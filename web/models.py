from typing import Optional
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    domains_detected: list[str]
    message: str = "Upload successful"


class GenerateRequest(BaseModel):
    upload_id: str
    domains: Optional[list[str]] = None
    study_name: Optional[str] = None
    global_macro_refs: Optional[list[str]] = None
    rag_enabled: bool = False
    rag_mock: bool = False
    lint_enabled: bool = False
    kb_path: Optional[str] = None


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str


class DomainDetail(BaseModel):
    domain: str
    status: str
    output_file: Optional[str] = None
    error: Optional[str] = None
    lint_issues: list[dict] = Field(default_factory=list)


class StatusResponse(BaseModel):
    job_id: str
    status: str  # pending / running / success / failed
    progress: float = Field(ge=0.0, le=1.0, default=0.0)
    study_name: Optional[str] = None
    total_domains: int = 0
    completed_domains: int = 0
    details: list[DomainDetail] = Field(default_factory=list)
    batch_report_path: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    error: Optional[str] = None


class HistoryItem(BaseModel):
    id: str
    study_name: str
    upload_id: str
    domains: list[str]
    status: str
    generated_at: str
    output_dir: Optional[str] = None


class HistoryListResponse(BaseModel):
    items: list[HistoryItem]
    total: int


class ErrorResponse(BaseModel):
    detail: str
