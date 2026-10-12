# ADR-0008: FastAPI for the API; Celery with Redis for background work

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Capsule §13 stack; async-first API, heavy work must be asynchronous (rule 12); consistent with the reference project's FastAPI/Redis usage.

## Decision
FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic. Celery workers per queue (ingest, evaluate, analysis, notify, webhooks, monitor) plus beat for schedules. Redis as broker, result backend, cache, rate-limit store.

## Consequences
Mature ecosystem and team familiarity. Celery has operational quirks (visibility timeout, idempotency required) addressed by idempotency keys and the outbox.

## Alternatives considered
Arq/Dramatiq (viable, smaller ecosystem); Temporal (powerful but heavier than V1 needs; revisit for complex workflows).
