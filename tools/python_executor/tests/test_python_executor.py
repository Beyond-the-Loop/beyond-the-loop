import json
import os
from typing import List, Dict

import pytest

from tools.python_executor.main import run_python_code, app

try:
    # FastAPI test client
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - fallback if fastapi not installed
    TestClient = None  # type: ignore

def test_run_python_code_timeout():
    code = "import time\ntime.sleep(2)\n"
    result = run_python_code(code, timeout=1)
    assert result["success"] is False
    assert "timed out" in result["stderr"].lower()
    assert result["stdout"] == ""
