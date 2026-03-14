#!/bin/bash


function log {
    echo [$(date "+%Y-%m-%d-%H:%M:%S")] "[INFO      ]: LOG:" $@
}

log "Starting ingestion of Country Data..."

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

 uv run src/batch_main.py --ingestion-type="country" --project-path=$ROOT

log "Country ingestion Completed.."