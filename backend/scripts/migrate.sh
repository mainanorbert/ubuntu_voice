#!/usr/bin/env bash
# Apply all pending Alembic migrations to the configured database.
# Usage: ./scripts/migrate.sh
#
# The script reads the database URL from the environment automatically.
# Make sure DATABASE_URL or EIVEN_SERVICE_URL is exported (or .env is loaded).
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -o allexport
  # shellcheck disable=SC1091
  source <(tr -d '\r' < .env)
  set +o allexport
fi

exec uv run alembic upgrade head
