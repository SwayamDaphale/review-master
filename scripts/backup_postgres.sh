#!/usr/bin/env bash
set -euo pipefail

# Review Master — Automated PostgreSQL Backup Script
# Creates a timestamped, compressed custom-format dump of the primary PostgreSQL database.

BACKUP_DIR="${1:-backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/reviewmaster_backup_${TIMESTAMP}.dump"
DB_NAME="${POSTGRES_DB:-reviewmaster}"
DB_USER="${POSTGRES_USER:-postgres}"

mkdir -p "${BACKUP_DIR}"

echo "==> Starting Review Master database backup..."
echo "    Database: ${DB_NAME}"
echo "    Target:   ${BACKUP_FILE}"

docker --context desktop-linux exec rm-postgres pg_dump \
  -U "${DB_USER}" \
  -Fc \
  --verbose \
  -d "${DB_NAME}" > "${BACKUP_FILE}" 2>/tmp/pg_dump_backup.log

if [ ! -s "${BACKUP_FILE}" ]; then
  echo "[-] ERROR: Backup failed! Output file is empty or missing." >&2
  cat /tmp/pg_dump_backup.log >&2
  exit 1
fi

FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[+] Backup successfully created: ${BACKUP_FILE} (${FILE_SIZE})"

# Retention pruning
echo "==> Pruning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "reviewmaster_backup_*.dump" -mtime +"${RETENTION_DAYS}" -exec rm -f {} \; || true
echo "[+] Backup process complete."

