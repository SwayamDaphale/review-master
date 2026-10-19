# ADR-0013: Tenant isolation with PostgreSQL Row-Level Security

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Capsule §33 requires tenant isolation; a sellable product with commercial API customers cannot risk cross-tenant leaks from one missed `WHERE` clause.

## Decision
Every tenant-owned table has `org_id` and an RLS policy driven by `SET app.current_org`; application checks remain. CI runs an isolation test suite.

## Consequences
Defense in depth. Adds per-request session setup and careful handling with connection pooling (use `SET LOCAL` inside transactions).

## Alternatives considered
Schema-per-tenant (rejected: operational overhead); application-only filtering (rejected: single point of failure).
