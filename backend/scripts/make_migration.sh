#!/usr/bin/env bash
# Auto-generate a new Alembic revision by comparing ORM metadata to the live DB.
# Usage: ./scripts/make_migration.sh "short description"
#
# Example: ./scripts/make_migration.sh "add company phone field"
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -z "${1:-}" ]; then
  echo "Usage: $0 <migration message>"
  exit 1
fi

if [ -f .env ]; then
  set -o allexport
  # shellcheck disable=SC1091
  source <(tr -d '\r' < .env)
  set +o allexport
fi

exec uv run alembic revision --autogenerate -m "$1"
