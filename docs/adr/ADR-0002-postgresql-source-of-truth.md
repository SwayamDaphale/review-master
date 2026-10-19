# ADR-0002: PostgreSQL 17 is the source of truth

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Capsule rule 13. Data is relational, audit-critical and needs transactions, constraints, partitioning, row-level security and full-text search.

## Decision
All durable state lives in PostgreSQL: catalog, evaluations, evidence metadata, auth, audit, outbox. Redis is rebuildable cache/queue. `pg_trgm` and full-text for V1 search. Monthly partitioning for `price_records`.

## Consequences
One system to back up, secure and reason about. Large price history may later need TimescaleDB or a replica; search may later need a dedicated engine. Both are additive.

## Alternatives considered
Document store (rejected: weak constraints for audit data); separate search or time-series DB in V1 (deferred until measured need).
