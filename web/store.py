import json
import threading
from pathlib import Path
from typing import Optional

from web.models import HistoryItem, StatusResponse


class JobStore:
    """JSON-backed persistent store for jobs and history."""

    def __init__(self, store_dir: Path):
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, dict] = {}
        self._history: list[dict] = []
        self._lock = threading.Lock()
        self._load()

    def _jobs_path(self) -> Path:
        return self.store_dir / "jobs.json"

    def _history_path(self) -> Path:
        return self.store_dir / "history.json"

    def _load(self) -> None:
        jobs_path = self._jobs_path()
        if jobs_path.exists():
            try:
                with open(jobs_path, "r", encoding="utf-8") as f:
                    self._jobs = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._jobs = {}

        history_path = self._history_path()
        if history_path.exists():
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    self._history = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._history = []

    def _save(self) -> None:
        with open(self._jobs_path(), "w", encoding="utf-8") as f:
            json.dump(self._jobs, f, indent=2, ensure_ascii=False)
        with open(self._history_path(), "w", encoding="utf-8") as f:
            json.dump(self._history, f, indent=2, ensure_ascii=False)

    def get_job(self, job_id: str) -> Optional[StatusResponse]:
        with self._lock:
            data = self._jobs.get(job_id)
        if not data:
            return None
        return StatusResponse.model_validate(data)

    def set_job(self, job_id: str, job: StatusResponse) -> None:
        with self._lock:
            self._jobs[job_id] = job.model_dump()
            self._save()

    def get_history(self, limit: int = 50, offset: int = 0) -> list[HistoryItem]:
        with self._lock:
            items = self._history[offset:offset + limit]
        return [HistoryItem.model_validate(i) for i in items]

    def append_history(self, item: HistoryItem) -> None:
        with self._lock:
            self._history.insert(0, item.model_dump())
            self._save()

    def delete_history(self, record_id: str) -> bool:
        with self._lock:
            original_len = len(self._history)
            self._history = [h for h in self._history if h.get("id") != record_id]
            changed = len(self._history) != original_len
            if changed:
                self._save()
        return changed

    def history_total(self) -> int:
        with self._lock:
            return len(self._history)
