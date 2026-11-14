#!/bin/sh
export PYTHONDONTWRITEBYTECODE=1
ROOT=$(cd "$(dirname "$0")" && pwd)
PYTHONPATH="$ROOT/src" exec python3 -m depgraph "$@"
