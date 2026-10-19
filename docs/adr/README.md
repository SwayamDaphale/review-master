# Architecture Decision Records

Short records of the decisions that shape Review Master. Status: **Accepted** (settled by the capsule or user requirements), **Proposed** (needs confirmation), **Assumed** (working assumption). New decisions get the next number; superseded ones are marked, never deleted.

| ADR | Title | Status |
|---|---|---|
| [0001](ADR-0001-modular-monolith-first.md) | Start as a modular monolith | Accepted |
| [0002](ADR-0002-postgresql-source-of-truth.md) | PostgreSQL 17 is the source of truth | Accepted |
| [0003](ADR-0003-deterministic-evaluation.md) | The evaluation engine is deterministic; the LLM is never the scoring authority | Accepted |
| [0004](ADR-0004-versioned-immutable-models.md) | Evaluation models are versioned and immutable once published | Accepted |
| [0005](ADR-0005-value-separate-from-quality.md) | Treat `value` as a separate, price-dependent signal | Proposed |
| [0006](ADR-0006-canonical-identity.md) | Canonical identity is separate from listings and offers; LLM output can never confirm a match | Accepted |
| [0007](ADR-0007-evidence-trust-tiers.md) | Evidence trust tier is fixed at ingestion | Accepted |
| [0008](ADR-0008-fastapi-celery-redis.md) | FastAPI for the API; Celery with Redis for background work | Accepted |
| [0009](ADR-0009-react-vite-spa.md) | React + Vite + TypeScript for the web app | Accepted |
| [0010](ADR-0010-litellm-gateway.md) | Route all LLM traffic through a gateway (LiteLLM) | Accepted |
| [0011](ADR-0011-s3-compatible-object-storage.md) | S3-compatible object storage; SeaweedFS locally; MinIO not used | Accepted |
| [0012](ADR-0012-builtin-auth-then-keycloak.md) | Built-in authentication first, behind an AuthProvider; Keycloak when enterprise SSO is needed | Accepted |
| [0013](ADR-0013-rls-multi-tenancy.md) | Tenant isolation with PostgreSQL Row-Level Security | Accepted |
| [0014](ADR-0014-transactional-outbox.md) | Events use a transactional outbox | Accepted |
| [0015](ADR-0015-qdrant-optional-rag.md) | Qdrant for RAG, optional; pgvector as the lean alternative | Accepted |
| [0016](ADR-0016-compose-profiles.md) | Docker Compose with profiles for optional services | Accepted |
| [0017](ADR-0017-github-actions-ci-cd.md) | GitHub Actions for CI/CD with a determinism gate | Assumed |
