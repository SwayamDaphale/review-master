# Review Master — Technology Stack and Architectural Inventory

**Status:** Living Architecture & Engineering Document  
**Version:** 1.0 (Phase B1 Baseline)  
**Last Updated:** November 2026  

---

## 1. Executive Overview

Review Master is an evidence-driven universal product review, evaluation, and recommendation platform. The system operates on strict separation of concerns:
- **Chromium Browser Extension (Manifest V3):** Collects raw DOM/HTML evidence and marketplace provenance directly from user-visited product listings.
- **FastAPI Backend (Python 3.12):** Enforces evidence schema validation, cleans and normalizes data, resolves canonical product identities, runs deterministic mathematical evaluation models, orchestrates LLM synthesis, and provides REST APIs.
- **PostgreSQL 17:** Primary relational database with ACID guarantees for product catalogs, spec definitions, evaluation runs, user reviews, and audit logs.
- **Redis 7 & Celery:** Task broker and result backend for asynchronous ingestion, scheduled re-scoring, and background processing.
- **SeaweedFS:** S3-compatible local object storage for raw HTML snapshots, images, and evidence payloads.
- **React 18 + Vite 6 + TypeScript Frontend:** Web application for catalog discovery, product comparisons, evaluation breakdowns, and interactive score exploration.

---

## 2. Approved Core Stack (V1 Phase Baseline)

| Component | Technology | Version | Rationale & Responsibility |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | FastAPI | `0.115.x` | High-performance asynchronous REST API framework with native Pydantic v2 validation and OpenAPI contract generation. |
| **Backend Language** | Python | `3.12` | Modern typing, performance improvements, and containerized consistency. |
| **Database Engine** | PostgreSQL | `17.4-alpine` | Relational store for canonical products, normalized specs, ratings, and audit records. |
| **Database Migrations** | Alembic | `1.14.x` | Programmatic schema migrations with versioned migration history. |
| **Database Driver** | Psycopg 3 | `3.2.x` | Modern, async-ready PostgreSQL driver with binary protocol support. |
| **ORM / Data Mapping** | SQLAlchemy | `2.0.x` | Clean declarative models with type hinting and statement generation. |
| **Cache & Task Broker** | Redis | `7.4-alpine` | Fast in-memory store for session caching, rate limiting, and Celery message queuing. |
| **Task Queue** | Celery | `5.4.x` | Asynchronous worker processing for extraction ingestion and batch scoring. |
| **Object Storage** | SeaweedFS | `3.86` | Lightweight, S3-compatible distributed object storage for raw HTML evidence snapshots. |
| **Cloud LLM Provider** | Groq API | Cloud API (`llama-3.3-70b-versatile`) | Ultra-fast cloud inference for synthesis, pros/cons extraction, and review summarization. |
| **Frontend Framework** | React | `18.3.1` | Component-based UI library with proven stability and ecosystem support. |
| **Frontend Tooling** | Vite | `6.2.x` | Fast development server and production bundler. |
| **Frontend Language** | TypeScript | `5.6.x` | Strict type safety across UI state and API response contracts. |
| **Frontend Styling** | Tailwind CSS | `3.4.x` | Utility-first CSS framework adhering to the design system. |
| **Browser Extension** | Manifest V3 | MV3 Standard | Chromium-compatible extension for privacy-conscious client-side evidence extraction. |

---

## 3. Explicitly Deferred Technologies & Architecture Decisions

To maintain focus, avoid unnecessary infrastructure overhead, and prevent premature scaling complexity in V1, several advanced technologies are explicitly deferred:

| Deferred Technology | Replacement in V1 | Evaluation Milestone & Reason for Deferral |
| :--- | :--- | :--- |
| **Apache Kafka** | Redis + Celery | Celery on Redis easily handles the ingestion throughput of V1 (< 500 req/sec). Kafka introduces severe operational overhead (Zookeeper/KRaft, partition management) unnecessary for V1. Re-evaluate when daily stream ingestion exceeds 5,000 events/sec. |
| **Qdrant Vector DB** | PostgreSQL (`pgvector` when needed) | Semantic vector search is deferred to Phase 2. V1 focuses on deterministic attribute-based evaluation and keyword indexing. Docker profile `rag` maintains a pinned placeholder. |
| **Neo4j Graph DB** | Relational Cross-References in Postgres | Product entity resolution and category hierarchies in V1 are modeled relationally. Graph traversals are deferred to V3 for multi-tier supply chain and accessory graphing. |
| **Keycloak IAM** | FastAPI JWT / Secure Session Tokens | V1 relies on scoped JWT tokens with cryptographic signature validation. Full enterprise OIDC/SSO via Keycloak is deferred to Phase 2. |
| **LiteLLM Multi-Proxy** | Direct Groq Client SDK | Direct Groq integration avoids unnecessary proxy hops, latency, and extra configuration layers in V1. LiteLLM proxy will be introduced when multi-model routing across multiple cloud vendors is needed. |

---

## 4. Docker Compose Topology and Service Profiles

The Review Master Docker deployment is organized into core runtime services and optional profiles to keep developer machines lightweight:

### 4.1 Port Allocations and Network Contracts

| Service Name | Container Internal Port | Host Published Port | Profile | Health Check / Validation |
| :--- | :--- | :--- | :--- | :--- |
| `postgres` | `5432` | `5433` *(avoids host conflict)* | Default | `pg_isready -U postgres` |
| `redis` | `6379` | `6380` *(avoids host conflict)* | Default | `redis-cli ping` |
| `seaweedfs` | `8333` (master/S3), `8888` (filer) | `8333`, `8888` | Default | Filer HTTP endpoint check |
| `backend` | `8000` | `8000` | Default | `curl -f http://localhost:8000/healthz` |
| `frontend` | `5173` | `5173` | Default | HTTP GET `/` |
| `migrate` | One-shot | N/A | Default | `alembic upgrade head` |
| `worker` | Background process | N/A | `celery` | `celery -A app.worker.celery_app inspect ping` |
| `beat` | Background process | N/A | `celery` | Process execution check |
| `mailpit` | `1025` (SMTP), `8025` (Web) | `1025`, `8025` | `dev` | HTTP GET `/` |
| `qdrant` | `6333` | `6333` | `rag` | HTTP GET `/healthz` |
| `ollama` | `11434` | `11434` | `local-ai` | HTTP GET `/api/tags` |
| `litellm` | `4000` | `4000` | `proxy` | HTTP GET `/health` |

### 4.2 Profiles Strategy
- **Default (`docker compose up`):** Boots only `postgres`, `redis`, `seaweedfs`, `backend`, and `frontend`.
- **`celery` Profile (`--profile celery`):** Starts Celery background workers and scheduler once task code is implemented.
- **`dev` Profile (`--profile dev`):** Starts auxiliary development tooling (Mailpit, pgAdmin).
- **`rag` / `local-ai` Profiles:** Kept offline during V1 development.

---

## 5. Backend Dependency and Environment Strategy

1. **Host Isolation:**
   - The developer machine's shared Python environments (e.g. `/home/swayam/AI_World/Environments/env_genai/`) are protected and preserved.
   - Development and testing of the backend are executed via containerized environments (`review-master-backend:dev`) or an explicitly authorized, project-scoped virtual environment (`backend/mr_env`).
   - Absolute paths to host environments must never be hardcoded in scripts or Dockerfiles.

2. **Clean Dependency Separation:**
   - `backend/requirements.txt`: Pin only direct, vetted runtime packages (FastAPI, Uvicorn, Pydantic, SQLAlchemy, Psycopg, Alembic, Redis, Celery, httpx).
   - `backend/requirements-dev.txt`: Test and static analysis tools (Pytest, pytest-cov, pytest-asyncio, ruff, mypy).
   - Bloat prevention: No unneeded ML frameworks (PyTorch, TensorFlow) inside the core backend container; LLM tasks run via Groq API.

---

## 6. Browser Extension Architecture & Permission Model

1. **Manifest V3 Conformance:**
   - Uses MV3 declarative background service workers and non-persistent lifecycle.
   - Scripts are cleanly divided: `manifest.json`, `popup/`, `content/`, and `background/`.

2. **Strict Host Permission Whitelist:**
   - Host permissions are strictly restricted to Amazon India domains:
     - `https://www.amazon.in/*`
     - `https://amazon.in/*`
   - Automated permission gate (`scripts/check-permissions.mjs`) validates permissions on every build and CI run. Wildcard `*://*/*` or `https://*/*` permissions are strictly prohibited.

3. **Extraction & Provenance:**
   - The extension collects raw page text, pricing, availability, and selector snapshots.
   - Content scripts do **not** perform heavy NLP or final scoring; they serialize an extraction payload and transfer it to the Review Master backend or frontend bridge.

---

## 7. Security and Reliability Constraints

1. **Secrets Management:**
   - Absolutely no real API keys, database passwords, or JWT secrets committed to Git.
   - In production (`APP_ENV=production`), the application strictly refuses to start if `JWT_SECRET` or `API_KEY_PEPPER` contain default development strings.
   - Logging mechanisms use `Settings.safe_summary()` to explicitly redact passwords and credentials.

2. **Cryptographic & Network Safety:**
   - Constant-time comparison (`secrets.compare_digest`) for API key and token verification to mitigate timing attacks.
   - Strict CORS policy: Configured via `CORS_ORIGINS` to allow only authorized frontend origins and local dev ports.
   - Non-destructive operations: Data volumes are persistent (`postgres_data`, `redis_data`, `seaweedfs_data`); destructive commands like `docker compose down -v` are strictly forbidden in standard workflows.
