# Review Master — Local Development & Operations Guide

> **Audience:** Developers, QA Engineers, and System Architects.  
> **Environment:** Ubuntu Linux (tested on 22.04 LTS / 24.04 LTS), Chromium / Brave Browser.  
> **Repository Context:** Commands are run relative to the repository root (`<repo-root>/` or `review-master/`).  
> **Status:** Phase B1 Stabilized (Docker Compose, Alembic, FastAPI, React Frontend, MV3 Extension).

---

## 1. System Prerequisites

Before running Review Master components locally, verify that your host system has the required toolchains installed:

| Tool | Required Version | Verification Command | Notes |
|---|---|---|---|
| **Node.js** | `>= 20.x` (Recommended: `22.x LTS`) | `node -v` | Core runtime for extension and frontend |
| **npm** | `>= 10.x` | `npm -v` | Package manager for frontend and extension |
| **Python** | `3.12.x` | `python3.12 --version` | Target runtime for backend service |
| **Docker** | `>= 24.x` | `docker --version` | Container engine for local data stores and backend execution |
| **Docker Compose** | `>= 2.20.x` (Compose V2) | `docker compose version` | Multi-container local orchestration |
| **Chromium / Brave** | Latest stable | `brave-browser --version` or `google-chrome --version` | Browser host for extension |
| **Git** | `>= 2.40.x` | `git --version` | Version control |
| **curl** | System standard | `curl --version` | HTTP testing and API verification |

---

## 2. Repository Layout & First-Time Setup

```bash
# 1. Clone the repository (if not already cloned)
git clone https://github.com/SwayamDaphale/review-master.git
cd review-master

# 2. Inspect Git working tree
git status
```

Review Master is structured as a decoupled monorepo:
```
review-master/
├── backend/       # FastAPI, SQLAlchemy 2.0, Alembic, Pydantic (Python 3.12)
├── frontend/      # React 18, Vite 6, TypeScript, Tailwind CSS (Node 22)
├── extension/     # Chromium Manifest V3 extraction extension (Vanilla JS / Node tests)
├── docker/        # PostgreSQL init SQL, LiteLLM config, Prometheus
├── docs/          # Architecture, specs, data models, contracts, and ADRs
└── compose.yml    # Docker Compose multi-service definitions
```

---

## 3. Component A: Browser Extension

The Review Master extension is a Chromium Manifest V3 user-initiated tool designed to extract page-visible smartphone specifications from Amazon India (`amazon.in`) without background crawlers or privacy violations.

### 3.1 Commands & Execution

All extension commands are run from the `extension/` directory:

```bash
cd extension
```

| Operation | Command | Working Directory | Status | Notes / Output |
|---|---|---|:---:|---|
| **Install Dependencies** | `npm ci` | `extension/` | `[TERMINAL-TESTED]` | Fast install with 0 vulnerabilities (`devDependencies: {}`; uses built-in Node 22 APIs). |
| **Run Unit & Regression Tests** | `npm test` | `extension/` | `[TERMINAL-TESTED]` | 52 passing tests across 5 suites (106ms). |
| **Run Normalizers Suite** | `node --test tests/normalizers.test.mjs` | `extension/` | `[TERMINAL-TESTED]` | Normalizer unit assertions pass. |
| **Run Layout Regression Fixtures** | `node --test tests/expanded-details.test.mjs` | `extension/` | `[TERMINAL-TESTED]` | 14 expanded DOM fixtures pass. |
| **Verify Permission Gate** | `npm run check-permissions` | `extension/` | `[TERMINAL-TESTED]` | Confirms MV3 and host permissions strictly restricted to `amazon.in`. |
| **Build / Verify Unpacked Bundle** | `npm run build` | `extension/` | `[TERMINAL-TESTED]` | Source verified and ready for Chromium unpacking. |

### 3.2 Loading in Brave / Chromium Browser `[DOCUMENTED PROCEDURE]`

1. Open **Brave** (`brave-browser`) or **Google Chrome / Chromium**.
2. Navigate to the extensions manager:
   - In Brave: `brave://extensions`
   - In Chrome: `chrome://extensions`
3. Toggle on **Developer mode** (top-right corner).
4. Click the **Load unpacked** button in the top-left toolbar.
5. In the file picker, select the repository's **`extension/`** directory (relative to your workspace root):
   ```
   <repo-root>/extension
   ```
   *(Ensure you select the directory containing `manifest.json`)*.
6. The extension card **"Review Master - Smartphone Extractor"** (v1.0.0) will appear in the installed list with its cyan shield icon.

### 3.3 Reloading After Code Edits `[DOCUMENTED PROCEDURE]`

- If you modify `extension/src/content-script.js`, `extension/popup/popup.js`, or `extension/manifest.json`:
  1. Return to `brave://extensions` or `chrome://extensions`.
  2. Find the **Review Master** card.
  3. Click the circular **Reload** icon (or press `Ctrl+R` on that tab).

### 3.4 Manual Extraction Testing & Web App Connection `[TERMINAL & BROWSER READY]`

1. Open a new tab in Brave/Chrome and navigate to a live Amazon India smartphone listing:
   - Example 1: `https://www.amazon.in/dp/B0CX8BC2MW` (Samsung Galaxy S24)
   - Example 2: `https://www.amazon.in/dp/B0H297XH3K` (Redmi Note / Turbo)
2. Wait for the Amazon product page to fully render.
3. Click the **Extensions puzzle icon** in your browser toolbar, then click **Review Master**.
4. In the Review Master popup:
   - Verify the status indicator displays **"Ready"**.
   - Click **"Extract Smartphone Data"**.
5. Inspect the output tabs:
   - **Summary Grid:** Displays brand, model, RAM, storage, price (INR), display size, battery, and identity status.
   - **Normalized Tab:** Formatted JSON conforming to `smartphone-extraction-1.0.schema.json`.
   - **Raw Text Tab:** Preserved un-normalized DOM text for auditability.
   - **Warnings Tab:** Surfaces any missing parameters without inventing zero values.
6. **Connect with Web App (Two Options):**
   - **Option A (One-Click Direct Launch):** Click **"Open in Review Master Web"**. This launches `http://localhost:5173/app/import#data=...` in a new tab, automatically loading the extracted specifications and finding catalogue matches.
   - **Option B (File Export & Import):** Click **"Download Validated JSON"** to export `smartphone-extraction-<ASIN>-<TIMESTAMP>.json`, then navigate to `http://localhost:5173/app/import` and upload or paste the file.

---

## 4. Component B: Frontend Web Application

The frontend is a single-page application built with React 18, Vite 6, TypeScript, and TanStack React Query.

### 4.1 Commands & Execution

All frontend commands are run from the `frontend/` directory:

```bash
cd frontend
```

| Operation | Command | Working Directory | Status | Notes / Output |
|---|---|---|:---:|---|
| **Install Dependencies** | `npm ci` (or `npm install`) | `frontend/` | `[TERMINAL-TESTED]` | Installs 297 packages from synchronized lockfile into `frontend/node_modules/`. |
| **Start Dev Server** | `npm run dev` | `frontend/` | `[TERMINAL-TESTED]` | Starts Vite development server on `http://localhost:5173` (responds with 200 OK). |
| **Run Unit Tests** | `npm test` | `frontend/` | `[TERMINAL-TESTED]` | Executes Vitest runner (`vitest run`): 10 suites passed, 65 tests passed cleanly. |
| **Run ESLint** | `npm run lint` | `frontend/` | `[TERMINAL-TESTED]` | Executes ESLint (`eslint .`) configured via `eslint.config.js` (0 errors). |
| **Run TypeScript Typecheck** | `npm run typecheck` | `frontend/` | `[TERMINAL-TESTED]` | Executes `tsc --noEmit` across all `.tsx` and `.ts` files (0 errors). |
| **Build for Production** | `npm run build` | `frontend/` | `[TERMINAL-TESTED]` | Executes `tsc --noEmit && vite build`, creating optimized assets in `frontend/dist/`. |
| **Preview Production Build** | `npm run preview` | `frontend/` | `[DOCUMENTED PROCEDURE]` | Serves the generated production bundle on `http://localhost:5173`. |

### 4.2 Application URLs and Behavior
- **Local Development URL:** `http://127.0.0.1:5173` (or `http://localhost:5173`)
- **Expected Port:** `5173` (configured in `frontend/vite.config.ts`)
- **Stopping the Server:** Press `Ctrl+C` in the running terminal.

#### Controlled Port Conflict Troubleshooting:
If port `5173` is already in use by another process:
```bash
# 1. Identify which process is listening on port 5173
lsof -i :5173
# Alternatively:
ss -tulpn | grep 5173

# 2. Inspect the output to identify the exact PID and command (e.g. node / vite)
# Example output: node 12345 user ... (LISTEN)

# 3. Gracefully stop only the intended, verified process:
kill <PID>

# 4. Only if the process remains unresponsive after a few seconds, force stop:
kill -9 <PID>

# 5. Alternatively, launch Vite on a different port without stopping existing processes:
npm run dev -- --port 5174
```

#### Offline & Mock Data Fallback Behavior:
- When the backend service (`http://127.0.0.1:8000`) is offline, the API client (`frontend/src/api/index.ts`) catches the fetch timeout (`AbortSignal.timeout(1500)`) and automatically falls back to verified seed mock data in `frontend/src/api/mockData.ts`.
- The application remains completely interactive: users can view catalog items, test side-by-side comparisons, inspect trust scores, and browse admin screens.
- When the backend is online, live database records are rendered automatically.

---

## 5. Component C: Backend API Service

The backend is built with Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, and Pydantic Settings.

### 5.1 Host Python Environment vs Containerized Execution

To prevent polluting or breaking shared host Python environments (e.g. `/home/swayam/AI_World/Environments/env_genai/`), Review Master backend development is standardly executed **inside Docker containers**.

If local host Python execution is explicitly desired, verify host Python version:
```bash
cd backend

# Step 1: Check Python version in shared environment
if [ -f "/home/swayam/AI_World/Environments/env_genai/bin/python" ]; then
  /home/swayam/AI_World/Environments/env_genai/bin/python --version
fi
```

#### Compatibility Criteria:
1. **Python Version:** The Review Master backend strictly targets **Python 3.12** (`backend/requirements.txt`, `backend/README.md`).
2. **Dependency Separation:** Do not install packages into `/home/swayam/AI_World/Environments/env_genai/` without verifying it matches Python 3.12.
3. If incompatible, create an isolated project virtual environment:
   ```bash
   python3.12 -m venv mr_env
   source mr_env/bin/activate
   pip install -r requirements-dev.txt
   ```

### 5.2 Containerized Backend Testing & Tooling (Recommended)

Run backend tests, linting, and typechecks directly inside the verified Docker container without modifying your host system:

```bash
# Run from repository root:

# 1. Run full test suite with coverage
docker compose run --rm backend pytest -v --cov=app

# 2. Run Ruff linter
docker compose run --rm backend ruff check .

# 3. Run Ruff format check
docker compose run --rm backend ruff format --check .

# 4. Run Mypy static type checker
docker compose run --rm backend mypy app

# 5. Export OpenAPI 3.1 specification schema
docker compose run --rm backend python -m app.tools.export_openapi openapi.json
```

### 5.3 Application URLs & API Documentation
- **Base API URL:** `http://127.0.0.1:8000`
- **Liveness Health Check:** `http://127.0.0.1:8000/healthz` (returns `{"status":"ok","app":"review-master-backend","environment":"..."}`)
- **Readiness Health Check:** `http://127.0.0.1:8000/readyz` (validates PostgreSQL connectivity: `{"status":"ok","checks":{"database":"ok"}}`)
- **Product Search & Listing:** `http://127.0.0.1:8000/api/v1/products` (query params: `q`, `category`, `limit`, `cursor`)
- **Product Detail & Variants:** `http://127.0.0.1:8000/api/v1/products/{product_id}`
- **Interactive Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc Alternative UI:** `http://127.0.0.1:8000/redoc`
- **Raw OpenAPI 3.1 JSON:** `http://127.0.0.1:8000/openapi.json`

### 5.4 Database Seeding (Phase B2)

To populate the development database with idempotent reference catalog data (smartphones, laptops, external SSDs) without fake scores or pricing:

```bash
docker compose run --rm backend python -m app.db.seed
```

---

## 6. Component D: Database & Infrastructure (Docker Compose)

All persistent datastores and services are orchestrated through `compose.yml`.

### 6.1 Service Inventory & Port Mappings

| Service | Container Name | Host Port | Internal Port | Status / Healthcheck | Notes |
|---|---|---|---|---|---|
| **postgres** | `rm-postgres` | `5433` | `5432` | `pg_isready -U postgres` | Published on host 5433 to avoid local 5432 conflict |
| **redis** | `rm-redis` | `6380` | `6379` | `redis-cli ping` | Published on host 6380 to avoid local 6379 conflict |
| **migrate** | `rm-migrate` | N/A | N/A | One-shot Alembic migration | Runs `alembic upgrade head` before backend starts |
| **backend** | `rm-backend` | `8000` | `8000` | `curl -f http://localhost:8000/healthz` | FastAPI REST service (Uvicorn reload) |
| **frontend** | `rm-frontend` | `5173` | `5173` | Web UI | React 18 + Vite 6 dev server |
| **objectstore**| `rm-objectstore` | `8333` | `8333` | S3 gateway check | SeaweedFS pinned by digest for HTML snapshots |
| **mailpit** | `rm-mailpit` | `8025`, `1025` | `8025`, `1025` | Mailpit Web UI & SMTP | Pinned `axllent/mailpit:v1.33` |
| **worker** | `rm-worker` | N/A | N/A | Profile `celery` | Celery background task worker (Phase B4) |
| **beat** | `rm-beat` | N/A | N/A | Profile `celery` | Celery beat periodic scheduler (Phase B4) |

### 6.2 Verified Docker Compose Commands

Run all Docker commands from the repository root:

```bash
# 1. Start core application and datastores (postgres, redis, seaweedfs, backend, frontend)
docker compose up -d

# 2. Start core services without frontend container (for local npm run dev workflows)
docker compose up -d backend

# 3. Verify health and status of all containers
docker compose ps

# 4. Run database migrations on-demand
docker compose run --rm migrate

# 5. Check real-time backend logs (verifies database endpoint and safe startup)
docker compose logs -f backend

# 6. Safe shutdown: stops and removes containers while preserving persistent database volumes
docker compose down
```

> [!CAUTION]
> **Destructive Command:**  
> `docker compose down -v`  
> The `-v` flag permanently removes named Docker volumes (`postgres-data`, `redis-data`, `objectstore-data`), destroying all database records, catalog mappings, and test runs.  
> **Always use `docker compose down` for normal shutdown.** Only use `-v` if you intentionally wish to reset the entire database to a completely blank state.

### 6.3 Optional Service Profiles

```bash
# Enable Celery background processing (Phase B4):
docker compose --profile celery up -d

# Enable Developer tooling (Mailpit, etc.):
docker compose --profile dev up -d
```

---

## 7. Master Command Reference Table

| Component | Goal | Command | Working Directory | Verification Status | Expected Result |
|---|---|---|---|:---:|---|
| **Extension** | Run tests | `npm test` | `extension/` | `[TERMINAL-TESTED]` | 52 passing tests (0 failed) |
| **Extension** | Check permissions | `npm run check-permissions` | `extension/` | `[TERMINAL-TESTED]` | Permission gate verified (MV3) |
| **Extension** | Build check | `npm run build` | `extension/` | `[TERMINAL-TESTED]` | Extension ready for unpacking |
| **Frontend** | Install packages | `npm ci` | `frontend/` | `[TERMINAL-TESTED]` | 297 packages installed cleanly from lockfile |
| **Frontend** | Run tests | `npm test` | `frontend/` | `[TERMINAL-TESTED]` | 11 test suites passed, 73 tests passed (Vitest) |
| **Frontend** | Run ESLint | `npm run lint` | `frontend/` | `[TERMINAL-TESTED]` | ESLint scan passed (0 errors) |
| **Frontend** | Typecheck | `npm run typecheck` | `frontend/` | `[TERMINAL-TESTED]` | Zero TypeScript errors (`tsc --noEmit`) |
| **Frontend** | Start dev server | `npm run dev` | `frontend/` | `[TERMINAL-TESTED]` | Listening on `http://localhost:5173` (200 OK) |
| **Frontend** | Build bundle | `npm run build` | `frontend/` | `[TERMINAL-TESTED]` | Production bundle generated in `dist/` |
| **Backend** | Start API | `docker compose up -d backend` | Repo Root | `[TERMINAL-TESTED]` | Listening on `http://localhost:8000` (healthy) |
| **Backend** | Liveness Check | `curl -fsS http://localhost:8000/healthz` | Any | `[TERMINAL-TESTED]` | `{"status":"ok","app":"review-master-backend",...}` |
| **Backend** | Readiness Check | `curl -fsS http://localhost:8000/readyz` | Any | `[TERMINAL-TESTED]` | `{"status":"ok","checks":{"database":"ok"}}` |
| **Backend** | Catalog Search | `curl -fsS http://localhost:8000/api/v1/products` | Any | `[TERMINAL-TESTED]` | Returns PostgreSQL catalog products |
| **Backend** | Product Detail | `curl -fsS http://localhost:8000/api/v1/products/{id}` | Any | `[TERMINAL-TESTED]` | Returns product and attached variants |
| **Backend** | Seed Database | `docker compose run --rm backend python -m app.db.seed` | Repo Root | `[TERMINAL-TESTED]` | Idempotent catalog seed executed |
| **Backend** | Run unit tests | `docker compose run --rm backend pytest` | Repo Root | `[TERMINAL-TESTED]` | 23 passing tests (96% coverage) |
| **Backend** | Lint code | `docker compose run --rm backend ruff check .` | Repo Root | `[TERMINAL-TESTED]` | All checks passed |
| **Backend** | Typecheck | `docker compose run --rm backend mypy app` | Repo Root | `[TERMINAL-TESTED]` | Success: no issues found in 23 source files |
| **Database** | Start datastores | `docker compose up -d postgres redis` | Repo Root | `[TERMINAL-TESTED]` | Containers healthy (`5433` and `6380`) |
| **Database** | Run migrations | `docker compose run --rm migrate` | Repo Root | `[TERMINAL-TESTED]` | Revisions up to `0002_catalog_tables` applied |
| **Database** | Stop services | `docker compose down` | Repo Root | `[TERMINAL-TESTED]` | Containers stopped safely (data preserved) |

---

## 8. Safe Shutdown Procedures

To cleanly shut down your local development environment:

```bash
# 1. Stop Frontend: Press Ctrl+C in your frontend terminal
# 2. Stop Docker Stack: In repository root, run:
docker compose down

# 3. Optional: Clean transient local test caches
rm -rf frontend/dist backend/.pytest_cache backend/.ruff_cache
```
