#!/usr/bin/env bash
# ClaimsFlow live-demo runner (Linux / macOS / Git Bash).
# Usage:  ./demo.sh [clean|mismatch|fraud|denial|all|status]
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND="$SCRIPT_DIR/backend"
CLAIMS="$SCRIPT_DIR/demo_claims"

# Locate Python — prefer the venv, fall back to system claimsflow on PATH.
if [[ -x "$BACKEND/.venv/Scripts/python.exe" ]]; then
  PY="$BACKEND/.venv/Scripts/python.exe"
elif [[ -x "$BACKEND/.venv/bin/python" ]]; then
  PY="$BACKEND/.venv/bin/python"
else
  echo "[ERROR] Python venv not found under backend/.venv"
  echo "Run:  cd backend && python -m venv .venv && .venv/bin/pip install -e .[dev]"
  exit 1
fi
CLI="$PY -m claimsflow.cli.main"

sep() { printf '\n============================================================\n'; }

run_clean() {
  sep
  echo " SCENARIO A - CLEAN APPROVAL  (asthma + spirometry)"
  echo " Expected: auto_approve with bilingual EOB"
  sep
  (cd "$BACKEND" && $CLI process "$CLAIMS/01_clean_approval.json")
}

run_mismatch() {
  sep
  echo " SCENARIO B - MISMATCH  (asthma diagnosis + brain MRI)"
  echo " Expected: human_review with AI reasoning explaining mismatch"
  sep
  (cd "$BACKEND" && $CLI process "$CLAIMS/02_mismatch_human_review.json")
}

run_fraud() {
  sep
  echo " SCENARIO C - FRAUD VELOCITY  (6 same-day same-procedure claims)"
  echo " Expected: first 5 auto_approve, 6th trips velocity+duplicate"
  echo "           and lands in fraud_hold"
  sep
  for f in 03a 03b 03c 03d 03e 03f; do
    echo
    echo "--- submitting ${f}_fraud_velocity.json ---"
    (cd "$BACKEND" && $CLI process "$CLAIMS/${f}_fraud_velocity.json")
    sleep 2
  done
}

run_denial() {
  sep
  echo " SCENARIO D - AUTO DENY  (dental claim on Bronze plan, OON)"
  echo " Expected: auto_deny via eligibility short-circuit"
  echo "           (plan does not cover dental)"
  sep
  (cd "$BACKEND" && $CLI process "$CLAIMS/04_out_of_network.json")
}

run_status() {
  sep
  echo " STATUS - last 10 decisions in the database"
  sep
  (cd "$BACKEND" && $PY -c "
from claimsflow.core.db import get_session_factory
from claimsflow.models import Decision
from sqlalchemy import select
s = get_session_factory()()
rows = s.scalars(select(Decision).order_by(Decision.decided_at.desc()).limit(10)).all()
print(f'{\"claim_id\":<18} {\"decision\":<28} {\"confidence\":>10}')
for r in rows:
    print(f'{r.claim_id:<18} {r.decision_type:<28} {r.confidence_score:>10.2f}')
")
  echo
  echo "Healthz:"
  curl -s http://localhost:8000/healthz || true
  echo
}

usage() {
  cat <<EOF

ClaimsFlow live-demo runner

Usage:  ./demo.sh <scenario>

Scenarios:
  clean      Submit 01 - asthma + spirometry      (auto_approve, bilingual EOB)
  mismatch   Submit 02 - asthma dx + brain MRI    (human_review with AI reasoning)
  fraud      Submit 03 - 6 same-procedure claims  (fraud_hold on the 6th)
  denial     Submit 04 - dental on Bronze plan    (auto_deny)
  all        Run all four scenarios with pauses between them
  status     Show last 10 decisions and backend healthz
EOF
}

case "${1:-help}" in
  clean)    run_clean ;;
  mismatch) run_mismatch ;;
  fraud)    run_fraud ;;
  denial|deny) run_denial ;;
  status)   run_status ;;
  all)
    run_clean;    echo; echo " --- pausing 3s ---"; sleep 3
    run_mismatch; echo; echo " --- pausing 3s ---"; sleep 3
    run_denial;   echo; echo " --- pausing 3s ---"; sleep 3
    run_fraud
    ;;
  *) usage ;;
esac
