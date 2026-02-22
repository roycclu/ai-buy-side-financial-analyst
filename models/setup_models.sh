#!/usr/bin/env bash
# Pull all catalog models from Ollama.
# Usage: bash models/setup_models.sh [llama|deepseek|all]
# Requires Ollama to be running: ollama serve

set -e

FILTER="${1:-all}"

pull_if_match() {
  local family="$1"
  local model_id="$2"
  if [[ "$FILTER" == "all" || "$FILTER" == "$family" ]]; then
    echo "Pulling $model_id ..."
    ollama pull "$model_id"
  fi
}

# Llama models
pull_if_match llama llama3.1:8b
pull_if_match llama llama3.3:70b
pull_if_match llama llama3.2:3b

# DeepSeek models
pull_if_match deepseek deepseek-r1:7b
pull_if_match deepseek deepseek-r1:14b
pull_if_match deepseek deepseek-r1:32b

echo "Done."
