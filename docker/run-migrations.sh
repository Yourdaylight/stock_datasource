#!/bin/bash
# Run pending ClickHouse migrations.
#
# Migrations are SQL files in docker/migrations/ named like:
#   001_create_system_structured_logs.sql
#   002_add_some_column.sql
#
# A tracking table (stock_datasource._migrations) records which ones have
# been applied.  This script is idempotent — safe to run on every start.
#
# Usage:
#   ./docker/run-migrations.sh          # run inside docker-compose (default host)
#   ./docker/run-migrations.sh <host>   # override ClickHouse host

set -euo pipefail

CH_HOST="${1:-stock-clickhouse}"
CH_PORT="${2:-8123}"
CH_USER="${3:-clickhouse}"
CH_URL="http://${CH_HOST}:${CH_PORT}"

echo "[migrations] ClickHouse at ${CH_URL}"

# --- Ensure tracking table exists ---
curl -sf "${CH_URL}/?user=${CH_USER}" --data-binary "
CREATE TABLE IF NOT EXISTS stock_datasource._migrations
(
    version     String,
    applied_at  DateTime DEFAULT now()
)
ENGINE = TinyLog
" || { echo "[migrations] WARNING: cannot create _migrations table (DB may not be ready yet)"; exit 0; }

# --- Get already-applied versions ---
APPLIED=$(curl -sf "${CH_URL}/?user=${CH_USER}" --data-binary \
    "SELECT version FROM stock_datasource._migrations" 2>/dev/null || echo "")

# --- Run pending migrations ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIG_DIR="${SCRIPT_DIR}/migrations"

if [ ! -d "${MIG_DIR}" ]; then
    echo "[migrations] No migrations directory found, skipping."
    exit 0
fi

PENDING=0
APPLIED_NOW=0

for sql_file in $(ls "${MIG_DIR}"/*.sql 2>/dev/null | sort); do
    VERSION=$(basename "${sql_file}" .sql)

    if echo "${APPLIED}" | grep -qxF "${VERSION}"; then
        continue
    fi

    PENDING=$((PENDING + 1))
    echo "[migrations] Applying ${VERSION} ..."

    if curl -sf "${CH_URL}/?user=${CH_USER}" --data-binary @"${sql_file}"; then
        # Record success
        curl -sf "${CH_URL}/?user=${CH_USER}" --data-binary \
            "INSERT INTO stock_datasource._migrations (version) VALUES ('${VERSION}')"
        echo "[migrations] ✓ ${VERSION} applied"
        APPLIED_NOW=$((APPLIED_NOW + 1))
    else
        echo "[migrations] ✗ ${VERSION} FAILED — stopping"
        exit 1
    fi
done

if [ "${PENDING}" -eq 0 ]; then
    echo "[migrations] All migrations up to date."
else
    echo "[migrations] Applied ${APPLIED_NOW}/${PENDING} migration(s)."
fi
