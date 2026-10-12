# Non-Functional Requirements, Scalability and Disaster Recovery

Source targets come from the capsule §45 (formal SRS). Where the capsule gives no number, this document **proposes** one and marks it `PROPOSED`. Proposed numbers are for discussion with the tech lead and should be replaced by measured values after the pilot. The capsule says: *"Do not invent accuracy or scale numbers before establishing a test baseline"* — so no accuracy or load figures are stated here.

---

## 1. Requirements table

| Area | Requirement | Source | Measurement |
|---|---|---|---|
| Performance | Common/cached product evaluation retrieval ≈ ≤ 2 s under expected load | Capsule §45 | p95 latency of `GET /variants/{id}/evaluation` and product lookup, per environment |
| Performance (uncached) | Evaluation retrieval p95 ≤ 4 s | PROPOSED | Same metric, cache-miss only |
| Performance (AI) | Explanation generation p95 ≤ 8 s; cached ≤ 2 s | PROPOSED | `ai_runs` latency; cache hit rate |
| Usability | Common actions ≈ ≤ 3 clicks | Capsule §45 | Usability review of key flows |
| Availability | "Appropriate to commercial SLA" | Capsule §45 | Pilot: 99.5% monthly (PROPOSED); commercial API: 99.9% (PROPOSED, decide per contract) |
| Scalability | App, DB, queue and evaluation layers scale | Capsule §45, §42 | Load test results; horizontal API and worker scaling |
| Browser support | Supported Chromium-based browsers, extensible | Capsule §45 | Automated extension tests on supported browsers |
| Observability | Logs, error tracking, performance monitoring, evaluation-quality monitoring, audit logs, integration health | Capsule §45 | Dashboards and alerts exist (see ARCHITECTURE_VIEWS §6) |
| Backup | Automated backups and **tested** restoration | Capsule §45 | Scheduled restore drill (§3) |
| AI reliability | Confidence-aware extraction, traceable evidence, deterministic core scoring, human correction | Capsule §45 | Determinism CI gate; grounding validation; correction workflow |
| Security | RBAC, least privilege, encrypted transport, secrets management, API auth, webhook signing, scopes, retention/deletion, admin logging, audit, tenant isolation | Capsule §33 | Security test suite (see TEST_STRATEGY) |

## 2. Capacity planning inputs (to fill before sizing infrastructure)

These numbers are unknown today and drive cost (see `COST_AND_EFFORT_ESTIMATE.md`). Replace the placeholders after the pilot scope is agreed.

| Input | Pilot assumption | Notes |
|---|---|---|
| Active users (weekly) | TBD | KPI "weekly active users" |
| Products evaluated (V1: 1 marketplace, 3 categories) | TBD | Drives evaluation and evidence volume |
| Lookups per active user per week | TBD | Drives API and cache load |
| Price observations per offer per day | TBD | Drives `price_records` growth (partitioned monthly) |
| Feedback items per product | TBD | Drives review-analysis jobs |
| LLM-backed requests per day | TBD | Drives AI cost; caching reduces it |

## 3. Backup and disaster recovery (PROPOSED targets)

| Item | Proposal |
|---|---|
| PostgreSQL | Managed service with automated daily backups **plus point-in-time recovery**; backup retention agreed with the business (starting point: 14–30 days) |
| RPO (max data loss) | ≤ 15 minutes for PostgreSQL (PITR); object storage versioning on |
| RTO (max downtime) | ≤ 4 hours for pilot; tighten for commercial SLA |
| Object storage (evidence) | Versioning enabled, cross-region or cross-account replication for production, lifecycle rules for old versions |
| Redis | Cache and queue; treated as rebuildable. Durable state lives in PostgreSQL (outbox, jobs). Persistence (AOF) helps recovery of queued tasks but is not the source of truth |
| Secrets / configuration | In a managed secret store; infrastructure defined as code so an environment can be recreated |
| Restore drill | Monthly automated restore into an isolated environment, followed by smoke tests and an integrity check (row counts, latest evaluation per variant). A backup that has not been restored is not a backup |
| Failover | Single-region primary with replica for V1; multi-region only if a contractual SLA requires it |
| Runbooks | Documented procedures for: DB restore, point-in-time recovery, secret rotation, adapter outage, LLM provider outage, accidental data deletion |

Audit data (`audit_log`, `ai_runs`, `evaluations`) is included in the same backups and must be restored consistently with the tables it references.

## 4. Scalability plan (capsule §42)

| Layer | First lever | Next lever |
|---|---|---|
| API | Horizontal scaling (stateless containers) | Autoscaling on latency/CPU |
| Workers | Scale per queue independently (ingest, evaluate, analysis, notify, webhooks) | Extract the hottest worker type into a service (see ARCHITECTURE_VIEWS §5) |
| PostgreSQL | Indexes, query tuning, connection pooling (e.g. PgBouncer), `price_records` monthly partitions | Read replica for reporting and read-heavy endpoints; TimescaleDB for price history if volume demands |
| Cache | Redis cache of evaluations and explanations | Larger instance / cluster |
| Evidence | Object storage | CDN/signed URLs for downloads |
| Search | PostgreSQL FTS + `pg_trgm` | Dedicated search engine on measured need |
| AI | Caching, model routing, per-tenant budgets at the gateway | Dedicated AI service, batch jobs |
| Adapters | Independent worker queues and rate budgets per marketplace | Separate ingestion service |

Load testing: before the pilot, run a load test on the lookup and evaluation endpoints with a production-like dataset; record p50/p95/p99 and the saturation point. Publish results next to this document.

## 5. Capacity and cost guardrails

- Per-request and per-tenant LLM budget (gateway + orchestrator).
- Rate limits per API key and plan.
- Retention jobs for `usage_events`, `notifications`, raw AI inputs.
- Alerts for queue backlog, storage growth rate and LLM spend.

## 6. Compliance and data governance

- Data retention and deletion controls (capsule §33); user export and deletion endpoints.
- Privacy law and marketplace terms of service affect extraction and storage: see `SECURITY_THREAT_MODEL.md` §5 and get legal review before building the first adapter.
