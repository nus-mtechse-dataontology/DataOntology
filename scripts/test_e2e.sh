#!/bin/bash
# Run e2e golden question tests against a local Postgres instance and real LLM.
#
# Fill in your credentials in scripts/local.env before running.
# Required services: PostgreSQL on localhost:5432 with seed data from resources/seed_local.sql

set -euo pipefail

# --- load credentials ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/local.env"
[[ -f "$ENV_FILE" ]] || { echo "ERROR: $ENV_FILE not found. Copy scripts/local.env.example to scripts/local.env and fill in your credentials."; exit 1; }
# shellcheck source=/dev/null
source "$ENV_FILE"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; exit 1; }

# --- resolve project root ---
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# --- check required env vars ---
[[ -z "${GEMINI_API_KEY:-}" ]] && err "GEMINI_API_KEY is not set."

# --- check postgres is reachable ---
log "Checking PostgreSQL connection..."
uv run python - <<'EOF' || err "PostgreSQL is not running on localhost:5432. Start it before running e2e tests."
import socket
s = socket.socket()
s.settimeout(2)
try:
    s.connect(("localhost", 5432))
    s.close()
except Exception as e:
    raise SystemExit(e)
EOF

export PROJECT_PATH="$ROOT"
log "PROJECT_PATH=$PROJECT_PATH"

log "Running e2e tests..."
uv run pytest -m e2e -v "$@"
