#!/bin/bash


function log {
    echo [$(date "+%Y-%m-%d-%H:%M:%S")] "[INFO      ]: LOG:" $@
}

log "Installing virtual environment for Data Ontology..."

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


if [[ $OS == $PATTERN* ]]; then
    log "Creating Virtual Environment"
    python -m venv "$ROOT/venv"

    log "Activating Virtual Environment"
    source "$ROOT/venv/Script/activate"

    log "Installing UV.."
    python -m pip install uv

    log "Installing Required Python Packages using UV"
    uv pip install -e ".[dev]"
else
    log "Creating Virtual Environment"
    python3.14 -m venv "$ROOT/venv"

    log "Activating Virtual Environment"
    source "$ROOT/venv/bin/activate"

    log "Installing UV.."
    pip3 install uv

    log "Installing Required Python Packages using UV"
    uv pip install -e ".[dev]"
fi

log "Installation Completed.."