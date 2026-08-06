#!/usr/bin/env bash
# Launch the full sweep: two Ollama servers (one per arm) + two runners,
# each in its own tmux session. Arms run in parallel; each arm is
# internally sequential (PRD-A execution constant).
#
# Usage: launch-sweep.sh [--recreate]
#   --recreate  kill pre-existing ollama-armA/ollama-armB tmux sessions and
#               start fresh pinned servers. Without it, an existing session
#               is a hard error: we cannot verify a stale server was started
#               with the pinned env (OLLAMA_NUM_PARALLEL=1 etc.).
#
# Prereqs: backend/experiments/results/manifest.json generated
#          (cd backend && python -m experiments.harness.manifest)
#          and all gates G0-G4 green.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO/backend"
PY="$BACKEND/.venv/bin/python"
MANIFEST="$BACKEND/experiments/results/manifest.json"
RECREATE="${1:-}"

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: $MANIFEST missing — generate it first:" >&2
  echo "  (cd $BACKEND && $PY -m experiments.harness.manifest)" >&2
  exit 1
fi

# F5: never adopt a pre-existing server session — its env is unverifiable.
for s in ollama-armA ollama-armB; do
  if tmux has-session -t "$s" 2>/dev/null; then
    if [[ "$RECREATE" == "--recreate" ]]; then
      echo "killing existing tmux session $s (--recreate)"
      tmux kill-session -t "$s"
    else
      echo "ERROR: tmux session '$s' already exists. A stale server may lack" >&2
      echo "the pinned env (OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1" >&2
      echo "OLLAMA_KEEP_ALIVE=-1). Re-run with --recreate to kill and restart" >&2
      echo "both server sessions, or kill them yourself first." >&2
      exit 1
    fi
  fi
done
# Duplicate runners would double-write the same journal — always refuse.
for s in runner-armA runner-armB; do
  if tmux has-session -t "$s" 2>/dev/null; then
    echo "ERROR: tmux session '$s' already exists — a runner is (or was)" >&2
    echo "active. Attach and check (tmux attach -t $s); kill it before relaunching." >&2
    exit 1
  fi
done

tmux new-session -d -s ollama-armA "bash $REPO/scripts/serve-armA.sh"
tmux new-session -d -s ollama-armB "bash $REPO/scripts/serve-armB.sh"

echo "waiting for both servers..."
# Arm A on :11437 (see serve-armA.sh: :11434 is owned by the unpinned
# systemd Ollama, which serves dev/analysis traffic only).
for port in 11437 11435; do
  until curl -sf "http://127.0.0.1:$port/api/version" >/dev/null; do sleep 1; done
  echo "  :$port up"
done

# Verify the digest on each server against the manifest (F3). The servers
# read the system model store (read-only for this user), so pull is a
# fallback for a missing/mismatched model only — and a drifted digest after
# pulling means the tag moved since pre-registration: never launch on it.
MODEL="$(cd "$BACKEND" && $PY -c 'from experiments.config import DEFAULT_CONFIG; print(DEFAULT_CONFIG.model)')"
EXPECTED="$($PY -c "import json; print(json.load(open('$MANIFEST'))['model_digest'])")"
digest_on() {
  curl -s "http://127.0.0.1:$1/api/tags" | $PY -c "
import json, sys
tags = json.load(sys.stdin).get('models', [])
print(next((m['digest'] for m in tags if m['name'] in ('$MODEL', '$MODEL:latest')), ''))
"
}
for port in 11437 11435; do
  ACTUAL="$(digest_on "$port")"
  if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "  :$port model missing or digest drift — pulling $MODEL"
    OLLAMA_HOST=127.0.0.1:$port ollama pull "$MODEL" || true
    ACTUAL="$(digest_on "$port")"
  fi
  if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "ERROR: model digest on :$port is '$ACTUAL' but manifest pins $EXPECTED." >&2
    echo "The tag has moved since pre-registration (or the pull failed on the" >&2
    echo "read-only store). Do NOT launch; investigate (the runner would" >&2
    echo "refuse too, unless --allow-digest-mismatch)." >&2
    exit 1
  fi
  echo "  :$port digest OK ($ACTUAL)"
done

tmux new-session -d -s runner-armA \
  "cd $BACKEND && $PY -m experiments.harness.runner --arm single 2>&1 | tee -a experiments/results/runner-single.log"
tmux new-session -d -s runner-armB \
  "cd $BACKEND && $PY -m experiments.harness.runner --arm mas 2>&1 | tee -a experiments/results/runner-mas.log"

echo "sweep launched. Watch: tmux attach -t runner-armA | runner-armB"
echo "progress: watch cat $BACKEND/experiments/results/progress.json"
