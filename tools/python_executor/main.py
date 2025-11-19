# app.py
import subprocess
import tempfile
import uuid
from datetime import timedelta
from io import BytesIO

from pathlib import Path
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64

app = FastAPI()

BUCKET_NAME = "python-executor"

class CodeRequest(BaseModel):
    code: str
    timeout: int = 10
    files: list[dict] | None = None


def upload_to_gcs(local_dir: Path, execution_id: str, request_file_names: list[str]) -> list[dict]:
    """Uploads all files from local_dir to GCS and returns signed URLs and Base64 URLs."""

    try:
        from google.cloud import storage
        from google import auth
        from google.auth.transport.requests import Request

        credentials, project_id = auth.default()
        credentials.refresh(Request())
        client = storage.Client()
    except Exception:
        return []

    bucket = client.bucket(BUCKET_NAME)
    file_infos = []

    for file_path in local_dir.iterdir():
        if file_path.is_file() and file_path.name != "script.py" and file_path.name not in request_file_names:
            blob_path = f"executions/{execution_id}/{file_path.name}"
            blob = bucket.blob(blob_path)
            blob.upload_from_filename(str(file_path))

            # Create signed URL valid for 10 minutes
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=10),
                service_account_email=credentials.service_account_email,
                access_token=credentials.token,
                method="GET"
            )

            # Read file content as a binary stream
            file_binary = None if file_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif"] else BytesIO(file_path.read_bytes())

            file_infos.append({
                "name": file_path.name,
                "url": url,
                "binary": file_binary
            })

    return file_infos

def run_python_code(code: str, timeout: int = 10, request_files=None):
    if request_files is None:
        request_files = []
    execution_id = str(uuid.uuid4())


    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        script_path = tmp / "script.py"
        script_path.write_text(code, encoding="utf-8")

        print("FOLGENDE BILDER WERDEN GESPEICHERT", request_files)

        if request_files:
            for f in request_files:
                name = f.get("name")
                content = f.get("content")
                if not name or not content:
                    continue
                try:
                    data = base64.b64decode(content)
                    (tmp / name).write_bytes(data)
                except Exception as e:
                    print(f"Failed to write file {name}: {e}")

        # show all files on local disk
        print("BILDER WERDEN AUSGELESEN")
        for file in tmp.iterdir():
            print(file)

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

            files = upload_to_gcs(tmp, execution_id, [] if request_files else map(lambda rf: rf.get("name"), request_files))

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
            print(e)
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
        return run_python_code(
            request.code,
            timeout=request.timeout,
            request_files=request.files
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
