# Review Master — Environment and Runtime Configuration Hardening

**Date:** 2026-11-13  
**Status:** Hardened & Validated  

---

## 1. Configuration Architecture

Review Master utilizes Pydantic v2 Settings (`app.core.config.Settings`) to load and validate all application parameters at startup.

### Core Principles
1. **Zero Production Secrets in Source Code:** Default placeholder secrets (`change-me-dev-only-...`) are strictly blocked when `APP_ENV=production`.
2. **Startup Validation Gate:** FastAPI lifespan aborts startup immediately if critical security parameters are missing or invalid in production mode.
3. **Automatic Secret Masking:** Logging and string representations (`settings.safe_summary()`, `__repr__`) redact database passwords, JWT secrets, and provider keys.
4. **Least-Privilege Networking:** CORS and trusted proxy lists reject broad wildcards (`*`) in production.

---

## 2. Environment Variables Matrix

| Variable | Type | Default (Dev) | Staging / Prod Requirement | Description |
| :--- | :--- | :--- | :--- | :--- |
| `APP_ENV` | `str` | `development` | `staging` or `production` | Active runtime environment. |
| `DEBUG` | `bool` | `true` | **`false`** | Enables FastAPI `/docs` and debug traceback display. Must be `false` in production. |
| `LOG_LEVEL` | `str` | `info` | `info` or `warning` | Logging verbosity (`debug`, `info`, `warning`, `error`). |
| `API_BASE_URL` | `str` | `http://localhost:8000` | Fully-qualified public URL | Public URL for API routing and redirects. |
| `CORS_ORIGINS` | `str` (comma-sep) | `http://localhost:5173,http://127.0.0.1:5173` | Exact domain(s) of web client | Allowed CORS origins. Never use `*` in production. |
| `DATABASE_URL` | `str` | `postgresql+psycopg://...` | Managed PostgreSQL connection string | Relational store connection string with credentials. |
| `REDIS_URL` | `str` | `redis://localhost:6379/0` | Managed Redis connection string | Redis cache and rate-limiting instance. |
| `CELERY_BROKER_URL` | `str` | `redis://localhost:6379/1` | Redis DB 1 | Message broker queue. |
| `CELERY_RESULT_BACKEND` | `str` | `redis://localhost:6379/2` | Redis DB 2 | Async task result backend. |
| `S3_ENDPOINT_URL` | `str` | `http://localhost:8333` | S3 / SeaweedFS endpoint | Evidence object storage gateway endpoint. |
| `S3_BUCKET_EVIDENCE` | `str` | `rm-evidence` | Production bucket name | Evidence document container. |
| `S3_ACCESS_KEY` | `str` | `devaccess` | Secret IAM access key | S3 access key. |
| `S3_SECRET_KEY` | `str` | `devsecret` | Secret IAM secret key | S3 secret key. |
| `JWT_SECRET` | `str` | `change-me-dev-only-...` | **Cryptographically random >= 32 chars** | HMAC-SHA256 secret for signing access tokens. |
| `API_KEY_PEPPER` | `str` | `change-me-dev-only` | **Cryptographically random secret** | Pepper string for client API key hashing. |
| `RATE_LIMIT_ENABLED` | `bool` | `true` | `true` | Controls server-side rate limiting. |
| `TRUSTED_PROXIES` | `str` (comma-sep) | `127.0.0.1,::1` | Reverse proxy IP / CIDR | Whitelist of reverse proxy IPs permitted to forward client IPs. |
| `SENTRY_DSN` | `str` | *(None)* | DSN URI (optional) | Error tracking project endpoint. |
| `GROQ_API_KEY` | `str` | *(None)* | Primary provider API key | Primary LLM inference provider for extraction/intelligence. |
| `NVIDIA_API_KEY` | `str` | *(None)* | Secondary provider API key | Fallback LLM inference provider. |

---

## 3. Production Deployment Hardening Checklist

Prior to approving a closed-beta staging or production launch, verify:
- [x] `APP_ENV=production` set in environment.
- [x] `DEBUG=false` confirmed (disables interactive docs and raw stack traces).
- [x] `JWT_SECRET` configured with 256 bits of high entropy (`openssl rand -hex 32`).
- [x] `API_KEY_PEPPER` configured with dedicated random entropy.
- [x] `CORS_ORIGINS` restricted to exact frontend hostname(s) (no wildcards).
- [x] `TRUSTED_PROXIES` configured to match the VPC ingress / load balancer CIDR.
- [x] Cookies configured with `Secure=true`, `HttpOnly=true`, and `SameSite=Lax`.
- [x] JSON structured logging active for automated log ingestion.
- [x] Database migration applied and verified at revision head.
- [x] Reverse proxy terminates TLS and forwards `X-Request-ID`.

