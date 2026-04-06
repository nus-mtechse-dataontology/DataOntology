#!/bin/bash
# Start local dev environment: FastAPI server + ngrok tunnel + Telegram webhook registration.
#
# Fill in your credentials in scripts/local.env before running.

set -euo pipefail

# --- load credentials ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/local.env"
[[ -f "$ENV_FILE" ]] || { echo "ERROR: $ENV_FILE not found. Copy scripts/local.env.example to scripts/local.env and fill in your credentials."; exit 1; }
# shellcheck source=/dev/null
source "$ENV_FILE"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
err()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; exit 1; }

# --- resolve project root ---
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# --- check required env vars ---
[[ -z "${GEMINI_API_KEY:-}" ]]     && err "GEMINI_API_KEY is not set."
[[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] && err "TELEGRAM_BOT_TOKEN is not set."
[[ -z "${POSTGRES_USER:-}" ]]      && err "POSTGRES_USER is not set."
[[ -z "${POSTGRES_PASSWORD:-}" ]]  && err "POSTGRES_PASSWORD is not set."

# --- write vault files ---
printf "%s" "$POSTGRES_USER"     > "$ROOT/vault/postgres.user"
printf "%s" "$POSTGRES_PASSWORD" > "$ROOT/vault/postgres.password"

# --- check ngrok is installed ---
command -v ngrok &>/dev/null || err "ngrok is not installed. Install it from https://ngrok.com/download"

export PROJECT_PATH="$ROOT"
log "PROJECT_PATH=$PROJECT_PATH"

# --- cleanup on exit ---
cleanup() {
    log "Stopping server and ngrok..."
    [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null || true
    [[ -n "${NGROK_PID:-}" ]]  && kill "$NGROK_PID"  2>/dev/null || true
}
trap cleanup INT TERM EXIT

# --- start FastAPI ---
log "Starting FastAPI server on port 8000..."
uv run python src/main.py &
SERVER_PID=$!

# --- start ngrok ---
log "Starting ngrok tunnel on port 8000..."
ngrok http 8000 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

# --- wait for ngrok API to be ready ---
log "Waiting for ngrok..."
for i in $(seq 1 15); do
    if curl -s http://localhost:4040/api/tunnels &>/dev/null; then
        break
    fi
    sleep 1
    [[ $i -eq 15 ]] && err "ngrok did not start in time. Check /tmp/ngrok.log"
done

# --- get ngrok public URL ---
NGROK_URL=$(uv run python - <<'EOF'
import urllib.request, json, sys
resp = urllib.request.urlopen("http://localhost:4040/api/tunnels")
data = json.loads(resp.read())
tunnels = data.get("tunnels", [])
https = [t for t in tunnels if t["proto"] == "https"]
url = https[0]["public_url"] if https else (tunnels[0]["public_url"] if tunnels else "")
if not url:
    print("ERROR: no tunnels found", file=sys.stderr)
    sys.exit(1)
print(url)
EOF
)
log "ngrok URL: $NGROK_URL"

# --- register Telegram webhook ---
WEBHOOK_URL="$NGROK_URL/ontology/telegram/webhook"
log "Registering Telegram webhook: $WEBHOOK_URL"

if [[ -n "${TELEGRAM_WEBHOOK_SECRET:-}" ]]; then
    PAYLOAD="{\"url\": \"$WEBHOOK_URL\", \"secret_token\": \"$TELEGRAM_WEBHOOK_SECRET\"}"
else
    PAYLOAD="{\"url\": \"$WEBHOOK_URL\"}"
fi

RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
log "Telegram response: $RESPONSE"

log ""
log "Local dev environment is ready"
log "  FastAPI : http://localhost:8000/ontology/docs"
log "  ngrok   : $NGROK_URL"
log "  Webhook : $WEBHOOK_URL"
log ""
log "Press Ctrl+C to stop."

# --- keep alive ---
set +e
wait $SERVER_PID
