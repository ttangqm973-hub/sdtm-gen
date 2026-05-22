import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class StudyConfig:
    """Study-level configuration for batch generation."""

    study_name: str
    domains: list[str] = field(default_factory=list)
    output_dir: str = "."
    global_macro_refs: list[str] = field(default_factory=list)
    rag_enabled: bool = False
    rag_mock: bool = False
    lint_enabled: bool = False
    kb_path: Optional[str] = None
    verbose: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "StudyConfig":
        # Filter to only known fields
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @classmethod
    def from_json(cls, path: str) -> "StudyConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
