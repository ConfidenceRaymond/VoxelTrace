#!/usr/bin/env bash
# Launch the VoxelTrace Streamlit app from the project venv.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_SERVER_HEADLESS="${STREAMLIT_SERVER_HEADLESS:-true}"
exec "$REPO/.venv/bin/streamlit" run "$REPO/app/Home.py" \
  --server.address "${VOXELTRACE_APP_ADDRESS:-127.0.0.1}" \
  --server.port "${VOXELTRACE_APP_PORT:-8501}" "$@"
