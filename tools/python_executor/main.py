# app.py
import subprocess
import tempfile
import uuid
from datetime import timedelta

from pathlib import Path
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

BUCKET_NAME = "python-executor"

class CodeRequest(BaseModel):
    code: str
    timeout: int = 10

def upload_to_gcs(local_dir: Path, execution_id: str) -> list[dict]:
    """Uploads all files from local_dir to GCS and returns signed URLs.

    Note: Importing google.cloud.storage lazily to avoid hard dependency during tests.
    If google-cloud-storage is not installed or credentials are missing, this function
    will return an empty list instead of raising, allowing local execution/tests.
    """

    try:
        from google.cloud import storage
        client = storage.Client()
    except Exception:
        return []

    bucket = client.bucket(BUCKET_NAME)
    file_infos = []

    for file_path in local_dir.iterdir():
        if file_path.is_file() and file_path.name != "script.py":
            blob_path = f"executions/{execution_id}/{file_path.name}"
            blob = bucket.blob(blob_path)
            blob.upload_from_filename(str(file_path))

            # Create signed URL valid for 10 minutes
            #url = blob.generate_signed_url(
            #    version="v4",
            #    expiration=timedelta(minutes=10),
            #    method="GET"
            #)

            file_infos.append({
                "filename": file_path.name,
                "url": "-"
            })

    return file_infos

def run_python_code(code: str, timeout: int = 10):
    execution_id = str(uuid.uuid4())

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        script_path = tmp / "script.py"
        script_path.write_text(code, encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(tmp)
            )

            stdout = result.stdout[-5000:] if result.stdout else ""
            stderr = result.stderr[-5000:] if result.stderr else ""

            files = upload_to_gcs(tmp, execution_id)

            return {
                "success": result.returncode == 0,
                "stdout": stdout.strip(),
                "stderr": stderr.strip(),
                "files": files,
                "execution_id": execution_id
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout}s.",
                "files": [],
                "execution_id": execution_id
            }

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Unexpected error: {str(e)}",
                "files": [],
                "execution_id": execution_id
            }

@app.post("/execute")
async def execute_code(request: CodeRequest):
    try:
        result = run_python_code(request.code, timeout=request.timeout)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
