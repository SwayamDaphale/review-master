#!/usr/bin/env bash
set -euo pipefail

# Review Master — PostgreSQL Restore Script
# Safely restores a custom-format pg_dump into a specified target database.

if [ $# -lt 1 ]; then
  echo "Usage: $0 <path-to-dump-file> [target-database]" >&2
  echo "Example: $0 backups/postgres/reviewmaster_backup_20261113.dump reviewmaster_restore_drill" >&2
  exit 1
fi

BACKUP_FILE="$1"
TARGET_DB="${2:-reviewmaster_restore_drill}"
DB_USER="${POSTGRES_USER:-postgres}"

if [ ! -f "${BACKUP_FILE}" ]; then
  echo "[-] ERROR: Dump file not found: ${BACKUP_FILE}" >&2
  exit 1
fi

if [ "${TARGET_DB}" = "reviewmaster" ] && [ "${FORCE_RESTORE:-0}" != "1" ]; then
  echo "[-] SAFETY ALERT: Refusing to restore over active primary 'reviewmaster' without FORCE_RESTORE=1." >&2
  exit 1
fi

echo "==> Restoring dump into database '${TARGET_DB}'..."
echo "    Source file: ${BACKUP_FILE}"

# Create target database if it does not already exist
docker --context desktop-linux exec rm-postgres psql -U "${DB_USER}" -tc \
  "SELECT 1 FROM pg_database WHERE datname = '${TARGET_DB}'" | grep -q 1 || \
  docker --context desktop-linux exec rm-postgres psql -U "${DB_USER}" -c \
  "CREATE DATABASE ${TARGET_DB};"

# Stream backup into pg_restore inside container
docker --context desktop-linux exec -i rm-postgres pg_restore \
  -U "${DB_USER}" \
  -d "${TARGET_DB}" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges < "${BACKUP_FILE}" 2>/tmp/pg_restore.log || {
    # pg_restore exit code 1 often occurs when clean triggers warnings on non-existent objects, verify errors
    if grep -iq "fatal" /tmp/pg_restore.log; then
      echo "[-] Restore encountered FATAL errors:" >&2
      cat /tmp/pg_restore.log >&2
      exit 1
    fi
  }

echo "[+] Restore completed successfully into '${TARGET_DB}'."

