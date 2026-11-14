# Review Master — Disaster Recovery, Backup and Restore Runbook

**Date:** 2026-11-13  
**Status:** Tested & Operational  
**Target RPO:** 1 hour  
**Target RTO:** 15 minutes  

---

## 1. Overview & Storage Scope

Review Master manages three categories of persistent data:

1. **Relational Source of Truth (PostgreSQL 17):**
   - Canonical catalog (categories, product families, products, variants).
   - Identity resolution matches and audit history.
   - Evidence records and extraction metadata.
   - Deterministic evaluations and parameter results (append-only, trigger-protected).
   - Comparison sessions and recommendation constraints.
   - User credentials, sessions, and single-use import handoff tokens.
2. **Evidence Documents & Raw Media (SeaweedFS Object Storage):**
   - S3-compatible bucket `rm-evidence`.
   - Immutable evidence snapshots and raw laboratory documents.
   - Referenced by SHA-256 hash in PostgreSQL `evidence_records`.
3. **Queue State & Rate Limiter Cache (Redis 7):**
   - Celery broker queues and result backend.
   - Rate-limiting sliding windows.
   - Configured with Append-Only File (`appendonly yes`) persistence.

---

## 2. PostgreSQL Backup & Restore

### Automated Backup Procedure

Execute the backup script from the repository root:
```bash
./scripts/backup_postgres.sh [destination_directory]
```
- **Default Location:** `backups/postgres/reviewmaster_backup_YYYYMMDD_HHMMSS.dump`
- **Format:** PostgreSQL Custom Format (`-Fc`), compressed, with full schema, triggers, and table data.
- **Retention:** Automatically prunes dumps older than 7 days (configurable via `RETENTION_DAYS`).

### Safe Restore Procedure

To restore into an isolated test database (recommended for verification):
```bash
./scripts/restore_postgres.sh backups/postgres/reviewmaster_backup_<timestamp>.dump reviewmaster_restore_drill
```

To restore over the primary database in a disaster recovery scenario:
```bash
FORCE_RESTORE=1 ./scripts/restore_postgres.sh backups/postgres/reviewmaster_backup_<timestamp>.dump reviewmaster
```
*(Requires `FORCE_RESTORE=1` safety guard to prevent accidental overwrite).*

---

## 3. SeaweedFS Object Storage Backup & Recovery

SeaweedFS stores evidence blobs under the persistent Docker volume `objectstore-data` (`/data`).

### Object Store Backup
1. **Filesystem Snapshot:**
   Back up the underlying Docker volume or directory:
   ```bash
   tar -czvf backups/seaweedfs/evidence_data_$(date +%Y%m%d).tar.gz -C /var/lib/docker/volumes/review-master_objectstore-data/_data .
   ```
2. **S3 Replication / Mirroring:**
   Using the AWS CLI or `rclone` with the local SeaweedFS endpoint:
   ```bash
   aws --endpoint-url http://localhost:8333 s3 sync s3://rm-evidence /backups/seaweedfs/rm-evidence/
   ```

### Object Store Recovery
1. Stop the object store service: `docker --context desktop-linux stop rm-objectstore`.
2. Extract the archive into the volume mount.
3. Start the service: `docker --context desktop-linux start rm-objectstore`.
4. Validate consistency between PostgreSQL `evidence_records` and SeaweedFS by querying evidence hashes.

---

## 4. Redis Durability & Recovery

Redis is configured in `compose.yml` with:
```yaml
command: ["redis-server", "--appendonly", "yes"]
```
- **AOF File:** Stored in Docker volume `redis-data` (`/data/appendonly.aof`).
- **Disaster Recovery:** In the event of a container restart, Redis automatically replays `appendonly.aof`.
- **Cache vs Business Data:** Rate-limiting counters and disposable cache keys expire naturally via TTL. Only durable Celery queue items require AOF recovery.

---

## 5. Live Restore Drill Verification Log

A full restore drill was conducted and verified on **2026-11-13**:
- **Script Executed:** `./scripts/restore_drill.sh`
- **Backup File Created:** `backups/postgres/reviewmaster_backup_20261113_093854.dump` (436 KB)
- **Target Drill Database:** `reviewmaster_restore_drill`

### Table Count Verification

| Table Name | Primary Database (`reviewmaster`) | Restored Database (`reviewmaster_restore_drill`) | Match Status |
| :--- | :--- | :--- | :--- |
| `products` | 464 | 464 | **MATCH** |
| `variants` | 467 | 467 | **MATCH** |
| `evaluations` | 497 | 497 | **MATCH** |
| `parameter_results` | 308 | 308 | **MATCH** |
| `import_tokens` | 1 | 1 | **MATCH** |
| `categories` | 163 | 163 | **MATCH** |

### Immutability Trigger Persistence Verification

A direct SQL `UPDATE` was attempted against the restored `evaluations` table in `reviewmaster_restore_drill`:
```sql
UPDATE evaluations SET overall_score = 99.9 WHERE id = (SELECT id FROM evaluations LIMIT 1);
```
**Result:** Rejected with error:
```
ERROR: Table evaluations is append-only: updates and deletes are prohibited
CONTEXT: PL/pgSQL function prevent_append_only_modification() line 3 at RAISE
```
**Conclusion:** Database immutability triggers (Migration 0011) are preserved in the backup and restore stream.

