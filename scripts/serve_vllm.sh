#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

uv run --project "$REPO_ROOT" --group train vllm serve "$REPO_ROOT/models/qwen3-vl-cord-merged" \
  --served-model-name qwen3-vl-cord-merged \
  --host 0.0.0.0 \
  --port 8000 \
  --limit-mm-per-prompt '{"image":1,"video":0}' \
  --max-model-len 4096
