# Review Master — Operations, Health & Incident Recovery Runbook

**Date:** 2026-11-13  
**Status:** Operational Reference  

---

## 1. System Topology & Core Dependencies

```
[ Chromium Extension ] ──┐
                         ├──> [ Load Balancer / Reverse Proxy ]
[ React Web Client   ] ──┘                 │
                                           ▼
                                [ FastAPI API Backend (rm-backend) ]
                                      │          │
                 ┌────────────────────┼──────────┴───────────────┐
                 ▼                    ▼                          ▼
       [ PostgreSQL (rm-postgres) ] [ Redis (rm-redis) ] [ SeaweedFS (rm-objectstore) ]
                                           ▲
                                           │
                         [ Celery Workers & Beat (rm-worker, rm-beat) ]
```

---

## 2. Health Monitoring & Verification Commands

| Component | Target URL / Command | Healthy Response | Action if Unhealthy |
| :--- | :--- | :--- | :--- |
| **API Liveness** | `curl -fsS http://localhost:8000/healthz` | `{"status":"ok",...}` | Restart API container |
| **Database Readiness** | `curl -fsS http://localhost:8000/readyz` | `{"status":"ok","checks":{"database":"ok"}}` | Inspect PostgreSQL logs & connection pool |
| **PostgreSQL Engine** | `docker --context desktop-linux exec rm-postgres pg_isready -U postgres` | `accepting connections` | Check disk space, locks, and PostgreSQL logs |
| **Redis Cache/Queue** | `docker --context desktop-linux exec rm-redis redis-cli ping` | `PONG` | Check memory limits and AOF file integrity |
| **Celery Worker** | `docker --context desktop-linux exec rm-backend celery -A app.worker.celery_app inspect ping` | `pong` | Check Redis connectivity and worker CPU |
| **Celery Beat** | Container health check inspects process table | Exit code 0 | Restart Beat container |
| **Object Storage** | `curl -fsS http://localhost:8333` | XML or SeaweedFS status | Check disk usage on `objectstore-data` |

---

## 3. Routine Service Restart Procedures

### Restart API Backend
```bash
docker --context desktop-linux restart rm-backend
```
*Zero data loss. Takes ~3 seconds.*

### Restart Celery Worker & Beat
```bash
docker --context desktop-linux restart rm-worker rm-beat
```
*Running tasks finish or return to queue; beat restarts schedule tracking.*

### Safe Restart of Complete Stack
```bash
docker --context desktop-linux compose restart
```
*(Never use `docker compose down -v` as that deletes persistent volumes).*

---

## 4. Incident Response & Troubleshooting Playbooks

### Playbook 1: PostgreSQL Connection Pool Exhaustion
- **Symptom:** `/readyz` returns 503 Service Unavailable with `database: error`. API logs show `TimeoutError: QueuePool limit of size 5 overflow 10 reached`.
- **Diagnostic:**
  ```bash
  docker --context desktop-linux exec rm-postgres psql -U postgres -d reviewmaster -c \
    "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
  ```
- **Remediation:**
  1. Identify long-running transactions:
     ```bash
     docker --context desktop-linux exec rm-postgres psql -U postgres -d reviewmaster -c \
       "SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC LIMIT 5;"
     ```
  2. Terminate hung queries:
     ```bash
     docker --context desktop-linux exec rm-postgres psql -U postgres -d reviewmaster -c \
       "SELECT pg_terminate_backend(<pid>);"
     ```
  3. If persistent, restart backend to clear pool connections.

---

### Playbook 2: Celery Worker Queue Backlog
- **Symptom:** Ingestion jobs remain in `pending` or `processing` state for > 5 minutes.
- **Diagnostic:**
  ```bash
  docker --context desktop-linux exec rm-backend celery -A app.worker.celery_app inspect active
  docker --context desktop-linux exec rm-backend celery -A app.worker.celery_app inspect reserved
  ```
- **Remediation:**
  1. Check worker logs for unhandled exceptions or LLM timeouts:
     ```bash
     docker --context desktop-linux logs --tail=100 rm-worker
     ```
  2. If worker is deadlocked on external API, restart worker: `docker --context desktop-linux restart rm-worker`.
  3. Purge corrupted test queues if required in dev/staging:
     ```bash
     docker --context desktop-linux exec rm-backend celery -A app.worker.celery_app purge
     ```

---

### Playbook 3: Rate Limiting & Denial of Service Incident
- **Symptom:** Legitimate users report HTTP 429 Too Many Requests, or single IP flooding endpoints.
- **Diagnostic:**
  Inspect Redis keys matching `rate_limit:*`:
  ```bash
  docker --context desktop-linux exec rm-redis redis-cli --scan --pattern "rate_limit:*"
  ```
- **Remediation:**
  1. If an abusive IP is identified, block IP at reverse proxy / firewall level.
  2. To clear a falsely locked client IP in Redis:
     ```bash
     docker --context desktop-linux exec rm-redis redis-cli del "rate_limit:auth_login:ip:<client_ip>"
     ```

---

### Playbook 4: Database Migration Failure & Recovery
- **Symptom:** `alembic upgrade head` fails or encounters lock contention.
- **Rules:**
  1. **NEVER modify historical migrations 0001–0012.**
  2. Verify active locks on PostgreSQL tables before retrying:
     ```bash
     docker --context desktop-linux exec rm-postgres psql -U postgres -d reviewmaster -c \
       "SELECT relation::regclass, mode, granted FROM pg_locks WHERE NOT granted;"
     ```
  3. Inspect current database revision: `docker --context desktop-linux exec rm-backend alembic current`.

---

### Playbook 5: Complete Disaster Recovery (Database Loss)
- **Pre-requisite:** Verified dump from `./scripts/backup_postgres.sh`.
- **Procedure:**
  1. Ensure target PostgreSQL is healthy: `docker --context desktop-linux exec rm-postgres pg_isready -U postgres`.
  2. Restore from latest verified dump:
     ```bash
     FORCE_RESTORE=1 ./scripts/restore_postgres.sh backups/postgres/reviewmaster_backup_<timestamp>.dump reviewmaster
     ```
  3. Validate table counts and trigger persistence: `./scripts/restore_drill.sh`.
  4. Restart application services: `docker --context desktop-linux restart rm-backend rm-worker`.
  5. Validate readiness probe: `curl -fsS http://localhost:8000/readyz`.

