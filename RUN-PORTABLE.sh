#!/bin/bash

SCRIPT_DIR="$(dirname ${BASH_SOURCE[0]})"

cd "$SCRIPT_DIR"

if [[ -z "$SCRIPT_DIR" ]]; then
    echo "This code must be ran as a script"
    exit 1
fi

PYTHON="$SCRIPT_DIR/bin-portable/pypy3.11-v7.3.21-linux64/bin/python3"


if [[ ! -f "$PYTHON" ]]; then
    echo "Could not find python"
    exit 1
fi

"$PYTHON" -m bobsofexile.main
