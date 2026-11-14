# Review Master — Closed-Beta Release Checklist & Verification Gate

**Release Version:** `v1.0.0-beta.1`  
**Target Environment:** Staging & Closed-Beta Production  
**Date:** 2026-11-13  
**Status:** Ready for Final Acceptance Sign-off  

---

## 1. Release Artifacts & Source Provenance

| Artifact | Identifier / Provenance | Verification Gate | Status |
| :--- | :--- | :--- | :--- |
| **Git Branch / Commit** | Branch: `main` (Repository: `SwayamDaphale/review-master`) | Working tree clean, zero unapproved commits | **VERIFIED** |
| **Database Schema** | Revision: `0012_b10_comparison_recommendations` | Single head verified, migrations 0001–0012 immutable | **VERIFIED** |
| **Backend Base Image** | `python:3.12.9-slim` | Pinned in `backend/Dockerfile` | **VERIFIED** |
| **Frontend Base Image** | `node:22-alpine` / `nginx:1.27.4-alpine` | Pinned in `frontend/Dockerfile` | **VERIFIED** |
| **Object Storage** | `chrislusf/seaweedfs@sha256:c2658820e763294a9e9de...` | Immutable digest pinned in `compose.yml` | **VERIFIED** |
| **Database Image** | `postgres:17.4-alpine` | Pinned in `compose.yml` | **VERIFIED** |
| **Redis Image** | `redis:7.4-alpine` | Pinned in `compose.yml` | **VERIFIED** |
| **CI Actions** | Pinned to immutable commit SHAs | `.github/workflows/ci.yml` audited | **VERIFIED** |

---

## 2. Automated Test Verification Matrix

| Test Suite | Scope | Target | Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Backend B1–B11 Core** | Catalog, auth, intelligence, ingestion, identity, evaluations, comparisons, recommendations | 100% pass | 69 / 69 passed | **PASS** |
| **Backend B12 Security** | Auth rejection, token expiry, refresh rotation, cross-tenant isolation, SQL injection, bypass header rejection | 100% pass | 12 / 12 passed | **PASS** |
| **Backend B12 Idempotency**| Single-use token race condition (8 threads), concurrent comparison session limit | 100% pass | 2 / 2 passed | **PASS** |
| **Backend B12 Performance**| Liveness, readiness, search, detail, evaluation retrieval (< 2s SLA), requirement parse | p95 < 2000ms | 4 / 4 passed (Eval p95 = 24.0ms) | **PASS** |
| **Alembic Single-Head** | Migration discovery and revision chain | 1 single head | 1 / 1 passed | **PASS** |
| **Frontend Unit & UI** | Formats, identifiers, mock API, HTTP client, storage, auth guards, admin auth, trust components | 100% pass | 76 / 76 passed | **PASS** |
| **Frontend Build** | Production static bundle compilation (`tsc --noEmit && vite build`) | Zero errors | Clean build (963ms) | **PASS** |
| **Extension Unit & Specs** | Amazon India smartphone layouts, DOM extractors, normalizers, edge cases | 100% pass | 58 / 58 passed | **PASS** |
| **Extension Security** | Host scope rejection, Manifest V3 least privilege, error sanitization, XSS passivity | 100% pass | 5 / 5 passed | **PASS** |
| **Extension Permissions** | Host permissions restricted to `amazon.in` and `localhost` | Zero violations | Gate passed | **PASS** |

---

## 3. Data Integrity & Disaster Recovery Gate

- [x] **Automated Backup Created:** `scripts/backup_postgres.sh` successfully generated timestamped dump.
- [x] **Restore Drill Verified:** `scripts/restore_drill.sh` executed against isolated database `reviewmaster_restore_drill`.
- [x] **Record Count Concordance:**
  - `products`: 464 / 464 (100% match)
  - `variants`: 467 / 467 (100% match)
  - `evaluations`: 497 / 497 (100% match)
  - `parameter_results`: 308 / 308 (100% match)
  - `import_tokens`: 1 / 1 (100% match)
  - `categories`: 163 / 163 (100% match)
- [x] **Immutability Trigger Verified:** Direct `UPDATE` attempt on restored `evaluations` rejected by `prevent_append_only_modification()` trigger.
- [x] **SeaweedFS Object Recovery:** Documented in `docs/operations/BACKUP_AND_RESTORE.md`.

---

## 4. Security & Environment Configuration Gate

- [x] **Rate Limiter Hardened:** `X-Bypass-Rate-Limit` header vulnerability completely eliminated.
- [x] **IP Spoofing Protection:** `X-Forwarded-For` ignored unless peer IP matches `TRUSTED_PROXIES`.
- [x] **Atomic Redis Counters:** Sliding-window rate limiting uses atomic pipeline transactions.
- [x] **Endpoints Rate-Limited:** Login (10/min), Register (5/min), Refresh (20/min), Import Tokens (20/min), Search (60/min), Ingestion (30/min).
- [x] **Production Secret Guard:** Application refuses to start in `production` mode with default dev secrets.
- [x] **Structured Logging Active:** JSON log formatter with request ID correlation (`X-Request-ID`) and token/password scrubbing.
- [x] **Sentry Ready:** Optional error tracking configurable via `SENTRY_DSN` with sensitive header scrubbing.
- [x] **Manifest V3 Least Privilege:** Scoped strictly to `amazon.in` and local API.

---

## 5. Closed-Beta Boundaries & Access Controls

- **Beta Scope:** Amazon India Smartphones (`smartphones` category).
- **Registration Control:** Closed beta access is restricted to invited test cohorts; production configuration disables unrestricted self-registration without pre-approved invite codes or administrative whitelisting.
- **Provider Infrastructure:** Groq primary LLM inference with automatic NVIDIA NIM backup failover (no local Ollama required for cloud staging).
- **Rollback Procedure:** If a critical staging regression occurs, rollback to previous image tag using `docker compose up -d <previous-image-tag>` and restore database backup if schema was altered.

