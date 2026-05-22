import os
import time

import pytest
from fastapi.testclient import TestClient

from web.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def ae_spec_path():
    return os.path.join(os.path.dirname(__file__), "fixtures", "sample_ae_spec.csv")


class TestUpload:
    def test_upload_spec(self, client, ae_spec_path):
        with open(ae_spec_path, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("ae_spec.csv", f, "text/csv")},
            )
        assert response.status_code == 200
        data = response.json()
        assert "upload_id" in data
        assert data["filename"] == "ae_spec.csv"
        assert "domains_detected" in data
        assert len(data["domains_detected"]) >= 1

    def test_upload_no_file(self, client):
        response = client.post("/api/upload")
        assert response.status_code == 422


class TestGenerate:
    def test_generate_job(self, client, ae_spec_path):
        # Upload first
        with open(ae_spec_path, "rb") as f:
            upload_resp = client.post(
                "/api/upload",
                files={"file": ("ae_spec.csv", f, "text/csv")},
            )
        upload_id = upload_resp.json()["upload_id"]

        # Submit job
        response = client.post(
            "/api/generate",
            json={
                "upload_id": upload_id,
                "study_name": "TEST_WEB",
                "domains": ["AE"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_generate_invalid_upload(self, client):
        response = client.post(
            "/api/generate",
            json={"upload_id": "nonexistent"},
        )
        assert response.status_code == 404


class TestStatus:
    def test_get_status(self, client, ae_spec_path):
        # Upload and generate
        with open(ae_spec_path, "rb") as f:
            upload_resp = client.post(
                "/api/upload",
                files={"file": ("ae_spec.csv", f, "text/csv")},
            )
        upload_id = upload_resp.json()["upload_id"]

        gen_resp = client.post(
            "/api/generate",
            json={
                "upload_id": upload_id,
                "study_name": "TEST_STATUS",
                "domains": ["AE"],
            },
        )
        job_id = gen_resp.json()["job_id"]

        # Poll status
        max_wait = 30
        waited = 0
        while waited < max_wait:
            status_resp = client.get(f"/api/status/{job_id}")
            assert status_resp.status_code == 200
            status = status_resp.json()
            if status["status"] in ("success", "failed"):
                break
            time.sleep(0.5)
            waited += 0.5

        assert status["status"] == "success"
        assert status["job_id"] == job_id
        assert status["total_domains"] >= 1

    def test_status_not_found(self, client):
        response = client.get("/api/status/nonexistent")
        assert response.status_code == 404


class TestDownload:
    def test_download_domain(self, client, ae_spec_path):
        # Upload, generate, wait for completion
        with open(ae_spec_path, "rb") as f:
            upload_resp = client.post(
                "/api/upload",
                files={"file": ("ae_spec.csv", f, "text/csv")},
            )
        upload_id = upload_resp.json()["upload_id"]

        gen_resp = client.post(
            "/api/generate",
            json={
                "upload_id": upload_id,
                "study_name": "TEST_DL",
                "domains": ["AE"],
            },
        )
        job_id = gen_resp.json()["job_id"]

        # Wait for completion
        max_wait = 10
        waited = 0
        while waited < max_wait:
            status = client.get(f"/api/status/{job_id}").json()
            if status["status"] in ("success", "failed"):
                break
            time.sleep(0.5)
            waited += 0.5

        # Download
        response = client.get(f"/api/download/{job_id}/ae")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        content = response.content.decode("utf-8")
        assert "STUDYID" in content or "data sdtm." in content

    def test_download_all(self, client, ae_spec_path):
        # Upload, generate, wait for completion
        with open(ae_spec_path, "rb") as f:
            upload_resp = client.post(
                "/api/upload",
                files={"file": ("ae_spec.csv", f, "text/csv")},
            )
        upload_id = upload_resp.json()["upload_id"]

        gen_resp = client.post(
            "/api/generate",
            json={
                "upload_id": upload_id,
                "study_name": "TEST_DL_ALL",
                "domains": ["AE"],
            },
        )
        job_id = gen_resp.json()["job_id"]

        # Wait for completion
        max_wait = 10
        waited = 0
        while waited < max_wait:
            status = client.get(f"/api/status/{job_id}").json()
            if status["status"] in ("success", "failed"):
                break
            time.sleep(0.5)
            waited += 0.5

        response = client.get(f"/api/download/{job_id}/all")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

    def test_download_not_found(self, client):
        response = client.get("/api/download/nonexistent/xx")
        assert response.status_code == 404


class TestHistory:
    def test_get_history(self, client):
        response = client.get("/api/history")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_delete_history(self, client):
        # First add a record by running a job
        ae_spec = os.path.join(os.path.dirname(__file__), "fixtures", "sample_ae_spec.csv")
        with open(ae_spec, "rb") as f:
            upload_resp = client.post(
                "/api/upload",
                files={"file": ("ae_spec.csv", f, "text/csv")},
            )
        upload_id = upload_resp.json()["upload_id"]

        gen_resp = client.post(
            "/api/generate",
            json={
                "upload_id": upload_id,
                "study_name": "TEST_DEL",
                "domains": ["AE"],
            },
        )
        job_id = gen_resp.json()["job_id"]

        # Wait for completion
        max_wait = 10
        waited = 0
        while waited < max_wait:
            status = client.get(f"/api/status/{job_id}").json()
            if status["status"] in ("success", "failed"):
                break
            time.sleep(0.5)
            waited += 0.5

        # Delete
        response = client.delete(f"/api/history/{job_id}")
        assert response.status_code == 200

        # Verify deletion
        response = client.delete(f"/api/history/{job_id}")
        assert response.status_code == 404
