#!/bin/bash

set -euo pipefail

function log {
    echo [$(date "+%Y-%m-%d-%H:%M:%S")] "[INFO      ]: LOG:" $@
}

log "Starting ingestion of Flight Search..."

# Resolve the full path of this script, following all symlinks
SOURCE="${BASH_SOURCE[0]}"

while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done

SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" >/dev/null 2>&1 && pwd)"

echo "Script directory: $SCRIPT_DIR"

CURRENT_DIR=$(pwd)
SOURCE_DIR=$(dirname "$0")
REL_DIR="$CURRENT_DIR/$SOURCE_DIR"
OS=$(uname)
OSR=$(uname -r)

PATTERN="MINGW64"

cd $SCRIPT_DIR/..
ROOT=$(pwd)

log "Detected Platform $OS $OSR"
log "Detected Script Folder: $SCRIPT_DIR"
log "Detected Script Relative Folder: $REL_DIR"

MODE="${1:-print-only}"

if [ "$MODE" = "--with-db" ]; then
  uv run src/batch_main.py --ingestion-type="flight_search" --project-path="$ROOT"
else
  PYTHONPATH="$ROOT/src" PROJECT_PATH="$ROOT" uv run python - <<'PY'
import json
import logging.config
import os
from pathlib import Path

import requests
import yaml

from configurations.logger_config import LoggerConfig
from ingestion.source.api_source.api_ingestion import ApiIngestion


class FlightSearchPrintOnly(ApiIngestion):
    def _get_data(self):
        self._log.info("API Ingestion: Getting data")
        response = requests.Session().send(self._payload)
        print(f"HTTP {response.status_code}")
        try:
            self._result = response.json()
            print(json.dumps(self._result, indent=2))
        except ValueError:
            self._result = {"text": response.text}
            print(response.text)

    def _upload_to_db(self, response_payload: dict):
        return None


logging.config.dictConfig(LoggerConfig().logger_config)

root = Path(os.environ["PROJECT_PATH"])
with open(root / "datasets" / "flight_search.yml") as cf:
    config = yaml.safe_load(cf)

ingestion = FlightSearchPrintOnly(None, config)
ingestion.ingest()
PY
fi

log "Flight Search ingestion Completed.."
