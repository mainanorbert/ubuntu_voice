#!/usr/bin/env bash
# Run the full test suite.
# Usage: ./scripts/test.sh [extra pytest args]
set -euo pipefail

cd "$(dirname "$0")/.."

exec uv run pytest tests/ -v "$@"
