#!/usr/bin/env bash
# ClaimsFlow LIVE batch demo (Linux / macOS / Git Bash).
# Submits 10 mixed claims via a single Python process with ~2s gaps.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [[ -x "$SCRIPT_DIR/backend/.venv/Scripts/python.exe" ]]; then
  PY="$SCRIPT_DIR/backend/.venv/Scripts/python.exe"
elif [[ -x "$SCRIPT_DIR/backend/.venv/bin/python" ]]; then
  PY="$SCRIPT_DIR/backend/.venv/bin/python"
else
  echo "[ERROR] Python venv not found under backend/.venv"; exit 1
fi

"$PY" "$SCRIPT_DIR/tools/demo_live_runner.py"
