#!/usr/bin/env bash
# Budget-sensitivity track v2b queue (owner GO 2026-08-18).
# Waits for the muse@think single arm to seal, runs its seal checks, then for
# each @b32 registry key in the pre-registered order: manifest -> mini-gates ->
# both-arm sweep (single on :11437, mas on :11435, concurrent per protocol).
# A gate FAIL skips that model's sweep (recorded), never blocks the queue.
set -uo pipefail

REPO=/home/el/projects/msc-dissertation
B=$REPO/backend
PY=$B/.venv/bin/python
LOG=$B/experiments/budget-track-queue.log
cd "$B"

log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

# ---- 1. wait for the muse@think single arm to finish ------------------------
THINK=$B/experiments/results-muse-glimmer-30b-thinking
log "queue start; waiting for muse@think single arm to seal"
while pgrep -f "harness.runner --arm single --model muse-glimmer:30b@think" >/dev/null; do
  sleep 60
done
N=$(wc -l < "$THINK/journal-single.jsonl")
log "muse@think single runner exited at $N/1150"

# ---- 2. seal checks on the muse@think track (single-arm-only seal) ----------
$PY -m experiments.analysis.seal_checks "$THINK" > "$THINK/seal-checks.txt" 2>&1
log "seal checks written: $THINK/seal-checks.txt (exit $?)"

# ---- 3. the six pre-registered sweeps, in order -----------------------------
KEYS=(
  "qwen2.5:7b-instruct@b32"
  "granite4.1:8b@b32"
  "qwen3.5:9b@b32"
  "lfm2.5:8b@b32-think"
  "qwen3.5:9b@b32-think-budget"
  "gemma4:latest@b32"
)

for KEY in "${KEYS[@]}"; do
  DIR=$($PY -c "from experiments.config import config_for_model; print(config_for_model('$KEY').results_dir)")
  log "=== $KEY -> $DIR ==="

  $PY -m experiments.harness.manifest --model "$KEY" >> "$LOG" 2>&1 \
    || { log "MANIFEST FAIL $KEY — skipping"; continue; }

  if $PY -m experiments.harness.mini_gates --model "$KEY" >> "$LOG" 2>&1; then
    log "gates PASS $KEY"
  else
    log "gates FAIL $KEY — sweep skipped, evidence in $DIR/gates/"
    continue
  fi

  $PY -m experiments.harness.runner --arm single --model "$KEY" \
      >> "$B/experiments/$DIR/runner-single.log" 2>&1 &
  P1=$!
  $PY -m experiments.harness.runner --arm mas --model "$KEY" \
      >> "$B/experiments/$DIR/runner-mas.log" 2>&1 &
  P2=$!
  log "runners launched $KEY (single=$P1 mas=$P2)"
  wait $P1; R1=$?
  wait $P2; R2=$?
  S=$(wc -l < "$B/experiments/$DIR/journal-single.jsonl" 2>/dev/null || echo 0)
  M=$(wc -l < "$B/experiments/$DIR/journal-mas.jsonl" 2>/dev/null || echo 0)
  log "SWEEP DONE $KEY single=$S/1150($R1) mas=$M/1150($R2)"

  $PY -m experiments.analysis.seal_checks "$B/experiments/$DIR" \
      > "$B/experiments/$DIR/seal-checks.txt" 2>&1
  log "seal checks $KEY (exit $?)"
done

log "QUEUE COMPLETE"
