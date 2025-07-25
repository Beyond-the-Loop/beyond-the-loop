#!/usr/bin/env bash

# Script to run Alembic migrations with proper environment setup
# Usage: ./run_alembic.sh [alembic-command]
# ./run_alembic.sh current
# ./run_alembic.sh upgrade head
# ./run_alembic.sh revision -m "Your migration message"
# ./run_alembic.sh history

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}"
OPENWEBUI_DIR="${BACKEND_DIR}/open_webui"

# Check if virtual environment exists
VENV_PATH="${BACKEND_DIR}/venv/bin/python"
if [ ! -f "${VENV_PATH}" ]; then
    echo "Error: Virtual environment not found at ${VENV_PATH}"
    echo "Please create the virtual environment first"
    exit 1
fi

# Set up environment
export PYTHONPATH="${BACKEND_DIR}:${PYTHONPATH}"

# Change to the open_webui directory (where alembic.ini is located)
cd "${OPENWEBUI_DIR}" || {
    echo "Error: Could not change to directory ${OPENWEBUI_DIR}"
    exit 1
}

# Run the alembic command with all provided arguments
echo "Running: ${VENV_PATH} -m alembic $*"
"${VENV_PATH}" -m alembic "$@"
