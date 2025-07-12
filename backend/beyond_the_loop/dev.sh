#!/usr/bin/env bash

# Get absolute paths
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$( cd -- "${SCRIPT_DIR}/../.." &> /dev/null && pwd )

# Set the Python path to include the backend directory
export PYTHONPATH="${PROJECT_ROOT}/backend:${PYTHONPATH}"

PORT="${PORT:-8080}"

# Start the LiteLLM container in the background
cd "${PROJECT_ROOT}" || exit 1
docker-compose -f docker-compose-local.yaml up -d litellm

# Start the uvicorn server
cd "${PROJECT_ROOT}/backend" || exit 1
"${PROJECT_ROOT}/backend/venv/bin/uvicorn" open_webui.main:app --port "${PORT}" --host 0.0.0.0 --forwarded-allow-ips '*' --reload