from typing import Optional, Literal
from pydantic import BaseModel, Field


class Variable(BaseModel):
    seq: int
    name: str
    label: str
    type: Literal["Char", "Num"]
    length: int
    origin: Literal["CRF", "Assigned", "Derived", "Predecessor"]
    generation: Literal["template", "ai_required"]
    codelist: Optional[dict] = None
    algorithm: Optional[str] = None
    ai_context: Optional[dict] = None
    ai_generated_code: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_sources: list[str] = Field(default_factory=list)
    ai_warnings: list[str] = Field(default_factory=list)
    confidence_target: Optional[float] = None
    comment: Optional[str] = None


class DomainIR(BaseModel):
    domain: str
    domain_label: str
    source_sheet: str
    variables: list[Variable]
    primary_key: list[str] = Field(default_factory=list)
    macro_refs: list[str] = Field(default_factory=list)
    cross_domain_refs: list[str] = Field(default_factory=list)
    template_name: Optional[str] = None
    ai_summary: Optional[dict] = None
