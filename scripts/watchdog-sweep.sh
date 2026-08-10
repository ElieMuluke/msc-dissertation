#!/usr/bin/env bash
# Stall watchdog for a running sweep: monitors the two runner tmux sessions
# and the sweep's progress heartbeat, and relaunches ONLY dead/stalled
# runners (resume is journal-driven, so a relaunch is always safe). It
# NEVER touches the Ollama server sessions, never writes to journals, and
# never writes inside a results dir except via the relaunched runner's own
# `tee` log (the same command shape scripts/launch-sweep.sh uses).
#
# Usage:
#   scripts/watchdog-sweep.sh MODEL_KEY
#
#   MODEL_KEY  replication registry key (config.REPLICATION_MODELS), e.g.
#              "qwen3.5:9b@0.32.6" — the same key the sweep was launched
#              with. Selects that key's results dir/manifest/journals.
#
# Typically run in its own tmux session alongside the sweep:
#   tmux new-session -d -s watchdog "scripts/watchdog-sweep.sh 'qwen3.5:9b@0.32.6'"
#
# Behaviour (checked every 120 s):
#   - a runner tmux session (runner-armA=single, runner-armB=mas) being dead
#     while its arm's journal is short of the manifest total  -> relaunch it;
#   - progress.json mtime not advancing for 20 min AND an incomplete arm's
#     journal mtime also not advancing for 20 min             -> the runner
#     is wedged: kill that runner session and relaunch it.
#   - both journals at the manifest totals                    -> exit 0.
# Every action is logged with a UTC timestamp to
# backend/experiments/watchdog.log (the results dir's PARENT — never inside
# a results dir). After MAX_RESTARTS=5 relaunches the watchdog alarm-exits
# (exit 2) instead of restarting again: something structural is wrong and a
# human must look. Servers (ollama-armA/armB) are never restarted here —
# their pinned env cannot be verified from a script (see launch-sweep.sh F5).
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 MODEL_KEY   (replication registry key, e.g. 'qwen3.5:9b@0.32.6')" >&2
  exit 1
fi
MODEL="$1"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO/backend"
PY="$BACKEND/.venv/bin/python"

CHECK_INTERVAL_S=120
STALE_AFTER_S=1200          # 20 min without progress.json/journal mtime advance
MAX_RESTARTS=5

RESULTS_DIR="$(cd "$BACKEND" && $PY -c "from experiments.config import config_for_model; print(config_for_model('$MODEL').results_dir)")"
MANIFEST="$RESULTS_DIR/manifest.json"
LOG="$BACKEND/experiments/watchdog.log"   # parent of the results dirs

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: $MANIFEST missing — is '$MODEL' a launched sweep?" >&2
  exit 1
fi
TOTAL_SINGLE="$($PY -c "import json; print(json.load(open('$MANIFEST'))['totals']['single'])")"
TOTAL_MAS="$($PY -c "import json; print(json.load(open('$MANIFEST'))['totals']['mas'])")"
TOTAL_ALL=$((TOTAL_SINGLE + TOTAL_MAS))

log() {
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) watchdog[$MODEL] $*" | tee -a "$LOG"
}

session_for() {  # arm -> tmux session name (same mapping as launch-sweep.sh)
  case "$1" in
    single) echo "runner-armA" ;;
    mas)    echo "runner-armB" ;;
  esac
}

journal_lines() {  # arm -> completed run count (journal line count)
  local f="$RESULTS_DIR/journal-$1.jsonl"
  if [[ -f "$f" ]]; then wc -l < "$f"; else echo 0; fi
}

age_s() {  # file -> seconds since mtime; "missing" files count as infinitely old
  if [[ -f "$1" ]]; then
    echo $(( $(date +%s) - $(stat -c %Y "$1") ))
  else
    echo $((STALE_AFTER_S + 1))
  fi
}

relaunch() {  # arm — exact command shape from launch-sweep.sh (resume is journal-driven)
  local arm="$1" session
  session="$(session_for "$arm")"
  tmux new-session -d -s "$session" \
    "cd $BACKEND && $PY -m experiments.harness.runner --arm $arm --model '$MODEL' 2>&1 | tee -a '$RESULTS_DIR/runner-$arm.log'"
  log "RELAUNCHED $session (--arm $arm --model '$MODEL')"
}

RESTARTS=0
log "watchdog started (results=$RESULTS_DIR totals: single=$TOTAL_SINGLE mas=$TOTAL_MAS interval=${CHECK_INTERVAL_S}s stale=${STALE_AFTER_S}s max_restarts=$MAX_RESTARTS)"

while true; do
  DONE_SINGLE="$(journal_lines single)"
  DONE_MAS="$(journal_lines mas)"
  DONE_ALL=$((DONE_SINGLE + DONE_MAS))

  if (( DONE_ALL >= TOTAL_ALL )); then
    log "sweep complete ($DONE_ALL/$TOTAL_ALL journalled) — exiting"
    exit 0
  fi

  PROGRESS_STALE=0
  if (( $(age_s "$RESULTS_DIR/progress.json") > STALE_AFTER_S )); then
    PROGRESS_STALE=1
  fi

  for arm in single mas; do
    if [[ "$arm" == "single" ]]; then
      done_arm=$DONE_SINGLE; total_arm=$TOTAL_SINGLE
    else
      done_arm=$DONE_MAS; total_arm=$TOTAL_MAS
    fi
    if (( done_arm >= total_arm )); then
      continue  # this arm is finished; its dead session is expected
    fi

    session="$(session_for "$arm")"
    reason=""
    if ! tmux has-session -t "$session" 2>/dev/null; then
      reason="session $session dead ($done_arm/$total_arm done)"
    elif (( PROGRESS_STALE )) && \
         (( $(age_s "$RESULTS_DIR/journal-$arm.jsonl") > STALE_AFTER_S )); then
      reason="progress.json and journal-$arm.jsonl stale >$((STALE_AFTER_S / 60))min with session alive ($done_arm/$total_arm done)"
    fi
    [[ -z "$reason" ]] && continue

    if (( RESTARTS >= MAX_RESTARTS )); then
      log "ALARM: $reason — but restart budget ($MAX_RESTARTS) exhausted; exiting 2. Investigate manually."
      exit 2
    fi
    log "STALL: $reason"
    if tmux has-session -t "$session" 2>/dev/null; then
      # wedged-but-alive runner: kill ONLY the runner session (never servers)
      tmux kill-session -t "$session"
      log "killed wedged session $session"
    fi
    relaunch "$arm"
    RESTARTS=$((RESTARTS + 1))
    log "restart count: $RESTARTS/$MAX_RESTARTS"
  done

  sleep "$CHECK_INTERVAL_S"
done
