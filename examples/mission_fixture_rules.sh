#!/usr/bin/env bash
# Offline mission example (synthetic fixture)
set -euo pipefail
uv run adventurectl mission run \
  --pack fixtures/karakoram_mini \
  --interpreter rules \
  -p "Three days, Suzuki Swift, rivers and forests, hate crowds."
