import asyncio
import json
import sys
import tempfile
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

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
from web.store import JobStore

router = APIRouter()

# In-memory uploads cache (not persisted; files are temporary)
_uploads: dict[str, dict] = {}

TEMP_DIR = Path(tempfile.gettempdir()) / "sdtm_gen_web"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Persistent stores
store = JobStore(TEMP_DIR / "store")
_queues: dict[str, asyncio.Queue] = {}


def _generate_id() -> str:
    return str(uuid.uuid4())[:8]


def _run_job_sync(
    job_id: str,
    spec_path: str,
    config: StudyConfig,
    store: JobStore,
    queue: Optional[asyncio.Queue],
    loop: Optional[asyncio.AbstractEventLoop],
):
    """Synchronous background task to run batch generation."""
    job = store.get_job(job_id)
    if not job:
        return

    def _put_event(ev: dict) -> None:
        if queue and loop:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, ev)
            except RuntimeError:
                # Event loop closed (e.g., during tests or server shutdown)
                pass

    _put_event({"event": "start"})

    job.status = "running"
    job.progress = 0.0
    store.set_job(job_id, job)

    try:
        scheduler = BatchScheduler()

        def progress_cb(event_type: str, domain: str, completed: int, total: int) -> None:
            job.progress = completed / total if total > 0 else 0.0
            store.set_job(job_id, job)
            _put_event({"event": "progress", "domain": domain, "completed": completed, "total": total})

        result = scheduler.run(spec_path, config, progress_callback=progress_cb)

        if result["total_domains"] == 0:
            job.status = "failed"
            job.error = "未检测到有效的 Domain sheet，请检查 SPEC 文件格式（首行需包含 varname/variable/label 等列名）"
        else:
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
        store.set_job(job_id, job)

        store.append_history(
            HistoryItem(
                id=job_id,
                study_name=config.study_name,
                upload_id="",
                domains=config.domains,
                status=job.status,
                generated_at=datetime.now().isoformat(),
                output_dir=config.output_dir,
            )
        )

        _put_event({"event": "complete"})

    except Exception as e:
        tb = traceback.format_exc()
        print(f"Job {job_id} failed: {e}\n{tb}", file=sys.stderr)
        job.status = "failed"
        job.error = str(e)
        store.set_job(job_id, job)
        _put_event({"event": "error", "message": str(e)})


@router.post("/api/upload", response_model=UploadResponse)
async def upload_spec(files: list[UploadFile] = File(...)):
    """Upload one or more SPEC Excel/CSV files. All files stored in the same directory for SUPP pairing."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    upload_id = _generate_id()
    upload_dir = TEMP_DIR / "uploads" / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    filenames = []
    domains = []
    primary_spec_path = None

    for file in files:
        if not file.filename:
            continue
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        filenames.append(file.filename)

    # Detect domains from the first valid SPEC file (has Variable sheet)
    reader = ExcelReader()
    from batch.scheduler import _is_variable_sheet, BatchScheduler
    scheduler = BatchScheduler()

    for filename in filenames:
        file_path = upload_dir / filename
        try:
            sheets = reader.read(str(file_path))
            for name, rows in sheets.items():
                if _is_variable_sheet(rows):
                    actual_domain = scheduler._resolve_domain(name, str(file_path))
                    # Skip SUPPxx domains — they are auto-associated with parent domains
                    if actual_domain not in domains and not actual_domain.upper().startswith('SUPP'):
                        domains.append(actual_domain)
                    if primary_spec_path is None:
                        primary_spec_path = str(file_path)
        except Exception:
            pass

    if primary_spec_path is None and filenames:
        primary_spec_path = str(upload_dir / filenames[0])

    _uploads[upload_id] = {
        "path": primary_spec_path or str(upload_dir),
        "spec_dir": str(upload_dir),
        "filename": filenames[0] if len(filenames) == 1 else f"{len(filenames)} files",
        "filenames": filenames,
        "domains": domains,
    }

    return UploadResponse(
        upload_id=upload_id,
        filename=_uploads[upload_id]["filename"],
        domains_detected=domains,
        message=f"Uploaded {len(filenames)} file(s)",
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
    total_domains = len(config.domains) if config.domains else len(upload.get("domains", []))
    store.set_job(
        job_id,
        StatusResponse(
            job_id=job_id,
            status="pending",
            study_name=config.study_name,
            total_domains=total_domains,
        ),
    )
    _queues[job_id] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    # Start background task using threading for test compatibility
    t = threading.Thread(
        target=_run_job_sync,
        args=(job_id, upload["path"], config, store, _queues[job_id], loop),
    )
    t.start()

    return GenerateResponse(
        job_id=job_id,
        status="pending",
        message="Job submitted successfully",
    )


@router.get("/api/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """Get job status and progress."""
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/api/stream/{job_id}")
async def stream_status(job_id: str):
    """Stream job progress via Server-Sent Events."""
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = _queues.get(job_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Job stream not available")

    async def event_generator():
        while True:
            event = await queue.get()
            data = f"data: {json.dumps(event)}\n\n"
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
    job = store.get_job(job_id)
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
    job = store.get_job(job_id)
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
    items = store.get_history(limit, offset)
    return HistoryListResponse(items=items, total=store.history_total())


@router.delete("/api/history/{record_id}")
async def delete_history(record_id: str):
    """Delete a history record."""
    deleted = store.delete_history(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"message": "Record deleted"}


# Lazy-initialized RAG pipeline for KB uploads
_kb_pipeline = None


def _get_kb_pipeline(kb_path: str = "D:/Claude code/Knowlegde base"):
    """Get or create the RAG pipeline for knowledge base operations."""
    global _kb_pipeline
    if _kb_pipeline is None:
        from rag.pipeline import RAGPipeline
        _kb_pipeline = RAGPipeline(knowledge_base_path=kb_path)
    return _kb_pipeline


@router.post("/api/kb/upload")
async def kb_upload(file: UploadFile = File(...), kb_path: str = "D:/Claude code/Knowlegde base"):
    """Upload a single file to the knowledge base (incremental add)."""
    import os

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".sas", ".txt", ".xlsx", ".xls", ".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: .sas, .txt, .xlsx, .pdf",
        )

    kb_dir = TEMP_DIR / "kb_uploads"
    kb_dir.mkdir(parents=True, exist_ok=True)

    file_path = kb_dir / file.filename
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        pipeline = _get_kb_pipeline(kb_path)
        result = pipeline.add_to_knowledge_base(str(file_path))

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))

        return {
            "filename": file.filename,
            "status": result["status"],
            "chunks_added": result.get("chunks_added", 0),
            "total_count": result.get("total_count", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KB add failed: {str(e)}")
