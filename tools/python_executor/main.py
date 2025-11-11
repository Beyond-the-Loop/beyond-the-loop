# app.py
import subprocess
import tempfile
import uuid
from datetime import timedelta
import os
import base64

from pathlib import Path
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

BUCKET_NAME = "python-executor"

# Maximum size of a single input file staged into the executor (bytes)
MAX_INPUT_FILE_SIZE = int(os.getenv("EXECUTOR_MAX_INPUT_FILE_SIZE", str(20 * 1024 * 1024)))  # 20 MB default


def _sanitize_filename(name: str) -> str:
    # Remove any path components and restrict to safe characters
    name = os.path.basename(name)
    # Avoid reserved name for script
    if name.lower() == "script.py":
        name = f"input_{uuid.uuid4().hex[:8]}.dat"
    return name


class FileItem(BaseModel):
    name: str
    # Base64-encoded content of the file; preferred input method
    content: str | None = None


class CodeRequest(BaseModel):
    code: str
    timeout: int = 10
    # Optional list of files to stage before executing the code
    files: list[FileItem] | None = None


def upload_to_gcs(local_dir: Path, execution_id: str) -> list[dict]:
    """Uploads all files from local_dir to GCS and returns signed URLs.

    Note: Importing google.cloud.storage lazily to avoid hard dependency during tests.
    If google-cloud-storage is not installed or credentials are missing, this function
    will return an empty list instead of raising, allowing local execution/tests.
    """

    try:
        from google.cloud import storage

        client = storage.Client()
    except Exception as e:
        print(e)
        return []

    bucket = client.bucket(BUCKET_NAME)
    file_infos = []

    for file_path in local_dir.iterdir():
        if file_path.is_file() and file_path.name != "script.py":
            blob_path = f"executions/{execution_id}/{file_path.name}"
            blob = bucket.blob(blob_path)
            blob.upload_from_filename(str(file_path))

            # Create signed URL valid for 10 minutes
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=10),
                method="GET",
                query_parameters={"response-content-disposition": f"attachment; filename={file_path.name}"}
            )

            file_infos.append({
                "name": file_path.name,
                "url": url
            })

    return file_infos


def _write_input_files(tmp: Path, files: list[FileItem] | None) -> list[str]:
    written: list[str] = []

    print("files to upload", files)
    if not files:
        return written

    for item in files:
        try:
            filename = _sanitize_filename(item.name)

            target = tmp / filename

            if item.content:
                try:
                    raw = base64.b64decode(item.content, validate=True)
                except Exception:
                    # Try without validation fallback
                    raw = base64.b64decode(item.content)
                if len(raw) > MAX_INPUT_FILE_SIZE:
                    # Skip oversized file
                    continue
                target.write_bytes(raw)
                written.append(filename)
                continue
        except Exception:
            # Ignore individual file failures
            continue
    return written


def run_python_code(code: str, timeout: int = 10, files: list[FileItem] | None = None):
    execution_id = str(uuid.uuid4())

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        # Stage any provided input files first
        try:
            written_files = _write_input_files(tmp, files)
            print("Written files: ", written_files)
        except Exception as e:
            # Non-fatal; proceed without files
            print(e)
            pass

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

            files_out = upload_to_gcs(tmp, execution_id)

            return {
                "success": result.returncode == 0,
                "stdout": stdout.strip(),
                "stderr": stderr.strip(),
                "files": files_out,
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
        result = run_python_code(request.code, timeout=request.timeout, files=request.files)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
