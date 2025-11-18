from typing import List, Dict

import pytest

from tools.python_executor.main import run_python_code, app

try:
    # FastAPI test client
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - fallback if fastapi not installed
    TestClient = None  # type: ignore


def test_run_python_code_success(monkeypatch):
    # Arrange: monkeypatch upload_to_gcs to avoid any cloud dependency and to
    # assert that temp files created by the executed script are uploaded except script.py
    captured_files: List[Dict] = []

    def fake_upload_to_gcs(local_dir, execution_id, request_file_names):
        nonlocal captured_files
        files: List[Dict] = []
        for p in local_dir.iterdir():
            if p.is_file() and p.name != "script.py":
                files.append({"name": p.name, "url": f"memory://{execution_id}/{p.name}"})
        captured_files = files
        return files

    monkeypatch.setattr("tools.python_executor.main.upload_to_gcs", fake_upload_to_gcs)

    code = (
        "print('hello world')\n"
        "open('output.txt','w').write('done')\n"
    )

    # Act
    result = run_python_code(code, timeout=5)

    # Assert
    assert result["success"] is True
    assert result["stderr"] == ""
    assert result["stdout"] == "hello world"
    assert isinstance(result["execution_id"], str) and result["execution_id"]
    # File listing should include output.txt but not script.py
    assert any(f["name"] == "output.txt" for f in captured_files)
    assert not any(f["name"] == "script.py" for f in captured_files)


def test_run_python_code_error():
    code = "print('before');\n1/0\nprint('after')\n"
    result = run_python_code(code, timeout=5)
    assert result["success"] is False
    assert "ZeroDivisionError" in result["stderr"]
    # stdout should still contain printed text before the error
    assert "before" in result["stdout"]


def test_run_python_code_timeout():
    code = "import time\ntime.sleep(2)\n"
    result = run_python_code(code, timeout=1)
    assert result["success"] is False
    assert "timed out" in result["stderr"].lower()
    assert result["stdout"] == ""


@pytest.mark.skipif(TestClient is None, reason="FastAPI TestClient not available")
def test_execute_endpoint_integrates_success(monkeypatch):
    # Arrange: avoid real GCS
    def fake_upload_to_gcs(local_dir, execution_id, request_file_names):
        return []

    monkeypatch.setattr("tools.python_executor.main.upload_to_gcs", fake_upload_to_gcs)

    client = TestClient(app)
    payload = {"code": "print('ok')", "timeout": 5}

    # Act
    resp = client.post("/execute", json=payload)

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["stdout"] == "ok"
    assert data["stderr"] == ""
    assert isinstance(data["files"], list)
    assert isinstance(data["execution_id"], str) and data["execution_id"]
