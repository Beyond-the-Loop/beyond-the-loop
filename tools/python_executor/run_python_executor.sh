#!/usr/bin/env bash
# Run the Python Executor FastAPI service with Uvicorn.
#
# Usage (from repo root or any directory inside the repo):
#   tools/python_executor/run_python_executor.sh [--host 0.0.0.0] [--port 8001] [--reload]
#
# Environment variables (override defaults if corresponding flag not provided):
#   HOST   - default: 0.0.0.0
#   PORT   - default: 8001
#   RELOAD - default: false (set to 1/true/yes/on to enable)
#
# Notes:
# - You need uvicorn and fastapi installed in the current Python environment.
# - The script will attempt to use the current interpreter: `python` or `python3`.

set -euo pipefail

# --- Google Cloud Credentials ---
# Adjust this path to your actual service account key file
GOOGLE_CREDENTIALS_PATH="/Users/philszalay/Documents/code/beyond-the-loop/gcp_python_executor_key.json"

if [[ ! -f "$GOOGLE_CREDENTIALS_PATH" ]]; then
  echo "Error: Google credentials file not found at $GOOGLE_CREDENTIALS_PATH" >&2
  exit 1
fi

export GOOGLE_APPLICATION_CREDENTIALS="$GOOGLE_CREDENTIALS_PATH"
echo "Using GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS"

# --- End Google Cloud Credentials ---


# Choose a python interpreter
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  else
    echo "Error: Neither 'python' nor 'python3' found in PATH." >&2
    exit 1
  fi
fi

# Check that uvicorn is available in the selected interpreter
if ! "${PYTHON_BIN}" - <<'PY'
try:
    import uvicorn  # type: ignore
except Exception as e:
    raise SystemExit(1)
PY
then
  echo "Error: uvicorn is not installed in the current environment." >&2
  echo "Install it first, e.g.: pip install uvicorn fastapi" >&2
  exit 1
fi

# Defaults from environment if flags are not provided
DEFAULT_HOST="${HOST:-0.0.0.0}"
DEFAULT_PORT="${PORT:-8001}"
RELOAD_ENV="${RELOAD:-}"

# Helper to check if an arg is present in "$@"
arg_present() {
  local needle="$1"; shift
  for a in "$@"; do
    if [[ "$a" == "$needle"* ]]; then
      return 0
    fi
  done
  return 1
}

# If --host is not provided, add default from HOST env
if ! arg_present "--host" "$@"; then
  set -- "$@" --host "${DEFAULT_HOST}"
fi

# If --port is not provided, add default from PORT env
if ! arg_present "--port" "$@"; then
  set -- "$@" --port "${DEFAULT_PORT}"
fi

# If no explicit --reload flag provided, enable if RELOAD env looks truthy
if ! arg_present "--reload" "$@"; then
  shopt -s nocasematch || true
  if [[ "${RELOAD_ENV}" =~ ^(1|true|yes|y|on)$ ]]; then
    set -- "$@" --reload
  fi
  shopt -u nocasematch || true
fi

# Determine repo root (this script lives in tools/python_executor)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Run uvicorn against the module path
cd "${REPO_ROOT}"
exec "${PYTHON_BIN}" -m uvicorn tools.python_executor.main:app "$@"
