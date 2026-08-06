#!/usr/bin/env bash
# Dedicated Ollama server for arm A (single) on :11434, PRD-A env pinning.
# Run under tmux: scripts/launch-sweep.sh does this for you.
set -euo pipefail

export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_KEEP_ALIVE=-1

exec ollama serve
