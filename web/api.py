import asyncio
import sys
import tempfile
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from batch.scheduler import BatchScheduler
from batch.study_config import StudyConfig
from parser.excel_reader import ExcelReader
from web.models import (
    DomainDetail,
    GenerateRequest,
    GenerateResponse,
    HistoryItem,
    HistoryListResponse,
    StatusResponse,
    UploadResponse,
)

router = APIRouter()

# In-memory stores (will be replaced by persistent storage in later tasks)
_uploads: dict[str, dict] = {}
_jobs: dict[str, StatusResponse] = {}
_history: list[HistoryItem] = []
_queues: dict[str, asyncio.Queue] = {}

TEMP_DIR = Path(tempfile.gettempdir()) / "sdtm_gen_web"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _generate_id() -> str:
    return str(uuid.uuid4())[:8]


def _run_job_sync(job_id: str, spec_path: str, config: StudyConfig):
    """Synchronous background task to run batch generation."""
    job = _jobs[job_id]
    queue = _queues.get(job_id)

    job.status = "running"
    job.progress = 0.0

    try:
        scheduler = BatchScheduler()
        result = scheduler.run(spec_path, config)

        job.status = "success" if result["failed"] == 0 else "failed"
        job.progress = 1.0
        job.completed_domains = result["successful"]
        job.elapsed_seconds = result.get("elapsed_seconds")
        job.batch_report_path = result.get("batch_report_path")

        job.details = [
            DomainDetail(
                domain=d["domain"],
                status=d["status"],
                output_file=d.get("output_file"),
                error=d.get("error"),
                lint_issues=d.get("lint_issues", []),
            )
            for d in result.get("details", [])
        ]

        _history.append(HistoryItem(
            id=job_id,
            study_name=config.study_name,
            upload_id="",
            domains=config.domains,
            status=job.status,
            generated_at=datetime.now().isoformat(),
            output_dir=config.output_dir,
        ))

    except Exception as e:
        tb = traceback.format_exc()
        print(f"Job {job_id} failed: {e}\n{tb}", file=sys.stderr)
        job.status = "failed"
        job.error = str(e)


@router.post("/api/upload", response_model=UploadResponse)
async def upload_spec(file: UploadFile = File(...)):
    """Upload a SPEC Excel/CSV file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    upload_id = _generate_id()
    upload_dir = TEMP_DIR / "uploads" / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / file.filename
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Detect domains
    reader = ExcelReader()
    try:
        sheets = reader.read(str(file_path))
        from batch.scheduler import _is_variable_sheet
        domains = [
            name for name, rows in sheets.items()
            if _is_variable_sheet(rows)
        ]
    except Exception:
        domains = []

    _uploads[upload_id] = {
        "path": str(file_path),
        "filename": file.filename,
        "domains": domains,
    }

    return UploadResponse(
        upload_id=upload_id,
        filename=file.filename,
        domains_detected=domains,
    )


@router.post("/api/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """Submit a batch generation job."""
    upload = _uploads.get(request.upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    job_id = _generate_id()
    job_dir = TEMP_DIR / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    config = StudyConfig(
        study_name=request.study_name or "STUDY",
        domains=request.domains or upload.get("domains", []),
        output_dir=str(job_dir),
        global_macro_refs=request.global_macro_refs or [],
        rag_enabled=request.rag_enabled,
        rag_mock=request.rag_mock,
        lint_enabled=request.lint_enabled,
        kb_path=request.kb_path,
        verbose=False,
    )

    # Initialize job status
    _jobs[job_id] = StatusResponse(
        job_id=job_id,
        status="pending",
        study_name=config.study_name,
        total_domains=len(config.domains) if config.domains else len(upload.get("domains", [])),
    )
    _queues[job_id] = asyncio.Queue()

    # Start background task using threading for test compatibility
    t = threading.Thread(target=_run_job_sync, args=(job_id, upload["path"], config))
    t.start()

    return GenerateResponse(
        job_id=job_id,
        status="pending",
        message="Job submitted successfully",
    )


@router.get("/api/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """Get job status and progress."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/api/stream/{job_id}")
async def stream_status(job_id: str):
    """Stream job progress via Server-Sent Events."""
    if job_id not in _queues:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = _queues[job_id]

    async def event_generator():
        while True:
            event = await queue.get()
            data = f"data: {event}\n\n"
            yield data
            if event.get("event") in ("complete", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.get("/api/download/{job_id}/all")
async def download_all(job_id: str):
    """Download all generated files as a zip archive."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    import zipfile

    zip_path = TEMP_DIR / "jobs" / job_id / f"{job.study_name}_all.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for detail in job.details:
            if detail.output_file and Path(detail.output_file).exists():
                zf.write(
                    detail.output_file,
                    arcname=Path(detail.output_file).name,
                )
        # Include batch report if available
        if job.batch_report_path and Path(job.batch_report_path).exists():
            zf.write(
                job.batch_report_path,
                arcname=Path(job.batch_report_path).name,
            )

    return FileResponse(
        path=str(zip_path),
        filename=f"{job.study_name}_all.zip",
        media_type="application/zip",
    )


@router.get("/api/download/{job_id}/{domain}")
async def download_domain(job_id: str, domain: str):
    """Download a single generated SAS file."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    for detail in job.details:
        if detail.domain.upper() == domain.upper() and detail.output_file:
            file_path = Path(detail.output_file)
            if file_path.exists():
                return FileResponse(
                    path=str(file_path),
                    filename=f"{domain.lower()}.sas",
                    media_type="text/plain",
                )

    raise HTTPException(status_code=404, detail="File not found")


@router.get("/api/history", response_model=HistoryListResponse)
async def get_history(limit: int = 50, offset: int = 0):
    """Get generation history."""
    items = _history[offset:offset + limit]
    return HistoryListResponse(items=items, total=len(_history))


@router.delete("/api/history/{record_id}")
async def delete_history(record_id: str):
    """Delete a history record."""
    global _history
    original_len = len(_history)
    _history = [h for h in _history if h.id != record_id]
    if len(_history) == original_len:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": "Record deleted"}
