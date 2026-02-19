#!/bin/bash


function log {
    echo [$(date "+%Y-%m-%d-%H:%M:%S")] "[INFO      ]: LOG:" $@
}

function getPid {
    PID=$(ps -ef | grep python | awk '{print $2}')

    if [[ -n $PID ]]; then
        echo $PID
    else
        echo ""
    fi
}

log "Starting Data Ontology..."

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

VENV_FOLDER="$ROOT/venv"

if [[ $OS = $PATTERN* ]]; then
    log "Activating Virtual Environment"
    source $VENV_FOLDER/Script/activate

    log "Setting Project Path"
    export PROJECT_PATH=$ROOT

    log "Starting Data Ontology"
    python src/main.py </dev/null > "service.log" 2>&1 &

else
    log "Activating Virtual Environment"
    source $VENV_FOLDER/bin/activate

    log "Setting Project Path"
    export PROJECT_PATH=$ROOT

    log "Starting Data Ontology"
    python3 src/main.py </dev/null > "service.log" 2>&1 &
fi

sleep 60s

PID=$(getPid)

if [[ -n $PID ]]; then
    log "Data Ontology Started Successfully"
else
    log "Error: Data Ontology Failed to Start"
fi