#!/usr/bin/env bash
# Dedicated Ollama server for arm A (single) on :11437, PRD-A env pinning.
# Run under tmux: scripts/launch-sweep.sh does this for you.
#
# Port note (2026-08-06 gate day): PRD-A originally named :11434, but the
# machine's systemd Ollama (user `ollama`, unpinned env) owns :11434 and
# cannot be stopped without interactive sudo. Arm A therefore runs on
# :11437 (matching experiments/config.py); the systemd server on :11434
# becomes the dev/analysis server and MUST receive no sweep traffic.
#
# Model store: user `el` has no local store; the world-readable system
# store already holds the digest-pinned weights. Serving reads only.
set -euo pipefail

export OLLAMA_HOST=127.0.0.1:11437
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_KEEP_ALIVE=-1
export OLLAMA_MODELS=/usr/share/ollama/.ollama/models

exec ollama serve
