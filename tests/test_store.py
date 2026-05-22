import tempfile
from pathlib import Path

from web.store import JobStore
from web.models import StatusResponse, HistoryItem


class TestJobStore:
    def test_empty_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(Path(tmpdir))
            assert store.get_job("nonexistent") is None
            assert store.get_history() == []
            assert store.history_total() == 0

    def test_set_and_get_job(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(Path(tmpdir))
            job = StatusResponse(
                job_id="abc123",
                status="pending",
                study_name="TEST",
                total_domains=2,
            )
            store.set_job("abc123", job)

            loaded = store.get_job("abc123")
            assert loaded is not None
            assert loaded.job_id == "abc123"
            assert loaded.status == "pending"
            assert loaded.study_name == "TEST"
            assert loaded.total_domains == 2

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            store1 = JobStore(path)
            job = StatusResponse(
                job_id="persist01",
                status="success",
                study_name="PERSIST",
                total_domains=1,
                completed_domains=1,
                progress=1.0,
            )
            store1.set_job("persist01", job)
            store1.append_history(
                HistoryItem(
                    id="persist01",
                    study_name="PERSIST",
                    upload_id="",
                    domains=["AE"],
                    status="success",
                    generated_at="2026-01-01T00:00:00",
                )
            )

            # 新实例应能读取之前写入的数据
            store2 = JobStore(path)
            loaded_job = store2.get_job("persist01")
            assert loaded_job is not None
            assert loaded_job.status == "success"
            assert loaded_job.progress == 1.0

            assert store2.history_total() == 1
            hist = store2.get_history()
            assert len(hist) == 1
            assert hist[0].study_name == "PERSIST"

    def test_append_and_get_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(Path(tmpdir))
            store.append_history(
                HistoryItem(
                    id="h1",
                    study_name="S1",
                    upload_id="u1",
                    domains=["DM"],
                    status="success",
                    generated_at="2026-01-01T00:00:00",
                )
            )
            store.append_history(
                HistoryItem(
                    id="h2",
                    study_name="S2",
                    upload_id="u2",
                    domains=["AE", "LB"],
                    status="failed",
                    generated_at="2026-01-02T00:00:00",
                )
            )

            assert store.history_total() == 2
            items = store.get_history(limit=1, offset=0)
            assert len(items) == 1
            assert items[0].id == "h2"  # 新记录插入头部

            items_offset = store.get_history(limit=10, offset=1)
            assert len(items_offset) == 1
            assert items_offset[0].id == "h1"

    def test_delete_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(Path(tmpdir))
            store.append_history(
                HistoryItem(
                    id="del1",
                    study_name="S1",
                    upload_id="u1",
                    domains=["DM"],
                    status="success",
                    generated_at="2026-01-01T00:00:00",
                )
            )
            assert store.delete_history("del1") is True
            assert store.history_total() == 0
            assert store.delete_history("del1") is False

    def test_update_existing_job(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobStore(Path(tmpdir))
            job = StatusResponse(
                job_id="update01",
                status="pending",
                study_name="TEST",
                total_domains=3,
            )
            store.set_job("update01", job)

            job.status = "running"
            job.progress = 0.5
            store.set_job("update01", job)

            loaded = store.get_job("update01")
            assert loaded.status == "running"
            assert loaded.progress == 0.5
