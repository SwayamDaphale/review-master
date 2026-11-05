# Review Master — Local Development & Operations Guide

> **Audience:** Developers, QA Engineers, and System Architects.  
> **Environment:** Ubuntu Linux (tested on 22.04 LTS / 24.04 LTS), Chromium / Brave Browser.  
> **Repository Context:** Commands are run relative to the repository root (`<repo-root>/` or `review-master/`).

---

## 1. System Prerequisites

Before running Review Master components locally, verify that your host system has the required toolchains installed:

| Tool | Required Version | Verification Command | Notes |
|---|---|---|---|
| **Node.js** | `>= 20.x` (Recommended: `22.x LTS`) | `node -v` | Core runtime for extension and frontend |
| **npm** | `>= 10.x` | `npm -v` | Package manager for frontend and extension |
| **Python** | `3.12.x` | `python3.12 --version` | Target runtime for backend service |
| **Docker** | `>= 24.x` | `docker --version` | Container engine for local data stores |
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
├── backend/       # FastAPI, SQLAlchemy, Alembic, Pydantic (Python 3.12)
├── frontend/      # React 18, Vite, TypeScript, Tailwind/Vanilla CSS (Node 22)
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
| **Verify Permission Gate** | `npm run check-permissions` | `extension/` | `[TERMINAL-TESTED]` | Confirms MV3 and host permissions restricted to `amazon.in`. |
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

### 3.4 Manual Extraction Testing & Web App Connection `[PENDING MANUAL BROWSER VALIDATION]`

1. Open a new tab in Brave/Chrome and navigate to a live Amazon India smartphone listing:
   - Example 1: `https://www.amazon.in/dp/B0CX8BC2MW` (Samsung Galaxy S24)
   - Example 2: `https://www.amazon.in/dp/B0H297XH3K` (Redmi Turbo 5)
2. Wait for the Amazon product page to fully render.
3. Click the **Extensions puzzle icon** in your browser toolbar, then click **Review Master**.
4. In the Review Master popup:
   - Verify the status indicator displays **"Ready"**.
   - Click **"Extract Smartphone Data"**.
5. Inspect the output tabs:
   - **Summary Grid:** Displays brand, model, RAM, storage, price (INR), display size, battery, and identity status.
   - **Normalized Tab:** Formatted JSON conforming to `smartphone-extraction-1.0.schema.json`.
   - **Raw Text Tab:** Preserved un-normalized DOM text for auditability.
   - **Warnings Tab:** Surfaces any missing parameters (e.g., iPhone unstated RAM) without inventing zero values.
6. **Connect with Web App (Two Options):**
   - **Option A (One-Click Direct Launch):** Click **"Open in Review Master Web"**. This launches `http://localhost:5173/app/import#data=...` in a new tab, automatically loading the extracted specifications and finding catalogue matches.
   - **Option B (File Export & Import):** Click **"Download Validated JSON"** to export `smartphone-extraction-<ASIN>-<TIMESTAMP>.json`, then navigate to `http://localhost:5173/app/import` and upload or paste the file.

---

## 4. Component B: Frontend Web Application

The frontend is a single-page application built with React 18, Vite, TypeScript, and TanStack React Query.

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

### 5.1 Python Environment Evaluation & Setup

Do **not** automatically create a new virtual environment. Follow this controlled evaluation sequence:

```bash
cd backend

# Step 1: Check whether the existing shared Python environment exists and is compatible
if [ -f "/home/swayam/AI_World/Environments/env_genai/bin/python" ]; then
  /home/swayam/AI_World/Environments/env_genai/bin/python --version
fi
```

#### Compatibility Criteria:
1. **Python Version:** The Review Master backend strictly targets **Python 3.12** (`backend/requirements.txt`, `backend/README.md`).
2. **Dependency Compatibility:** Must satisfy the dependencies listed in `backend/requirements.txt` and `backend/requirements-dev.txt` without package conflicts.

#### Resolution Workflow:
- **Scenario A (Compatible):** If `/home/swayam/AI_World/Environments/env_genai/` runs Python 3.12 and is compatible:
  ```bash
  source /home/swayam/AI_World/Environments/env_genai/bin/activate
  pip install -r requirements-dev.txt
  ```
- **Scenario B (Incompatible or Missing):** If `/home/swayam/AI_World/Environments/env_genai/` does not exist or uses a different Python version (e.g. Python 3.10):
  - **Document the incompatibility** (e.g. "Shared environment uses Python 3.10; backend requires Python 3.12").
  - **Request approval** before creating a project-specific environment.
  - Upon approval, create and activate the project-local virtual environment:
    ```bash
    python3.12 -m venv mr_env
    source mr_env/bin/activate
    pip install -r requirements-dev.txt
    ```

*(To deactivate any active virtual environment later, simply run `deactivate`)*.

### 5.2 Commands & Execution

With the approved Python 3.12 environment activated in `backend/`:

| Operation | Command | Working Directory | Status | Expected Output |
|---|---|---|:---:|---|
| **Start FastAPI Server** | `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` | `backend/` | `[FUTURE STAGE]` | `Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)` |
| **Run Unit Tests** | `pytest tests/` | `backend/` | `[FUTURE STAGE]` | Pytest discovers and runs unit/config tests |
| **Run Determinism Gate** | `pytest -m golden` | `backend/` | `[FUTURE STAGE]` | Executes immutable golden evaluation tests |
| **Run Ruff Linter** | `ruff check app tests` | `backend/` | `[FUTURE STAGE]` | `All checks passed!` |
| **Run Ruff Format Check** | `ruff format --check app tests` | `backend/` | `[FUTURE STAGE]` | Zero formatting drift detected |
| **Run Mypy Typecheck** | `mypy app` | `backend/` | `[FUTURE STAGE]` | `Success: no issues found in X source files` |
| **Export OpenAPI Spec** | `python -m app.tools.export_openapi openapi.json` | `backend/` | `[FUTURE STAGE]` | Generates validated `openapi.json` |

*Note on Host Binding:* Ordinary local development uses `--host 127.0.0.1` to restrict access to the local loopback interface. Use `--host 0.0.0.0` only when external container or LAN access is explicitly needed.

### 5.3 Application URLs & API Documentation
- **Base API URL:** `http://127.0.0.1:8000`
- **Interactive Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc Alternative UI:** `http://127.0.0.1:8000/redoc`
- **Raw OpenAPI 3.1 JSON:** `http://127.0.0.1:8000/openapi.json`

### 5.4 Health & API Ingestion Testing (via curl) `[FUTURE STAGE]`

```bash
# 1. Test basic liveness
curl -s http://127.0.0.1:8000/healthz | jq .
# Expected: {"status": "ok"}

# 2. Test database readiness
curl -s http://127.0.0.1:8000/readyz | jq .
# Expected: {"status": "ready", "database": "connected"}

# 3. Ingest a smartphone extraction record (Stage 5 target)
curl -X POST http://127.0.0.1:8000/api/v1/listings/ingest \
  -H "Content-Type: application/json" \
  -d @../extension/tests/fixtures/sample_galaxy_s24.json | jq .
```

---

## 6. Component D: Database & Infrastructure

PostgreSQL 17 and Redis 7 are managed locally via Docker Compose.

### 6.1 Essential vs. Optional Services

| Service | Category | Container Name | Port Mapping | Description |
|---|---|---|---|---|
| **postgres** | **Essential** | `rm-postgres` | `5433:5432` | Canonical source of truth (PostgreSQL 17) |
| **redis** | **Essential** | `rm-redis` | `6379:6379` | Cache, rate limiter, Celery message broker |
| **migrate** | **Essential** | `rm-migrate` | N/A | One-shot Alembic database migration runner |
| **objectstore** | Optional | `rm-objectstore` | `8333:8333` | SeaweedFS S3-compatible document store |
| **mailpit** | Optional | `rm-mailpit` | `8025:8025` | Mock email web UI for verification links |
| **litellm** | Optional (`--profile llm-gateway`) | `rm-litellm` | `4000:4000` | Unified AI gateway proxy |
| **ollama** | Optional (`--profile local-llm`) | `rm-ollama` | `11434:11434`| Local LLM execution engine |

*Note:* The extension and frontend can run independently for development without starting Docker Compose.

### 6.2 Infrastructure Commands

Run all Docker commands from the repository root:

```bash
# 1. Copy the environment template (safe development defaults)
cp .env.example .env

# 2. Start essential data stores (PostgreSQL & Redis) [DOCUMENTED PROCEDURE]
docker compose up -d postgres redis

# 3. Verify container health [DOCUMENTED PROCEDURE]
docker compose ps
# Expected: rm-postgres (healthy), rm-redis (healthy)

# 4. Run database migrations [FUTURE STAGE - Stage 4 target]
docker compose run --rm migrate

# 5. Check PostgreSQL database logs [DOCUMENTED PROCEDURE]
docker compose logs -f postgres

# 6. Standard safe shutdown: preserves persistent database volumes [DOCUMENTED PROCEDURE]
docker compose down
```

> [!CAUTION]
> **Destructive Command:**  
> `docker compose down -v`  
> The `-v` flag permanently removes named Docker volumes (`postgres-data`, `redis-data`, `objectstore-data`), destroying all database records, user tables, and catalog mappings.  
> **Always use `docker compose down` for normal shutdown.** Only use `-v` if you intentionally wish to reset the entire database to a completely blank state.

---

## 7. Complete Local Development Workflow

Follow this step-by-step sequence to run Review Master locally across multiple terminal tabs.

### Terminal 1: Infrastructure (PostgreSQL & Redis) `[DOCUMENTED PROCEDURE]`
```bash
# Run from repository root
docker compose up -d postgres redis
docker compose ps
```

### Terminal 2: Backend API (FastAPI) `[FUTURE STAGE]`
```bash
# Run from repository root
cd backend
# Activate approved environment:
source /path/to/approved_env/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Verify: Open `http://127.0.0.1:8000/docs` in your browser.*

### Terminal 3: Frontend Web Dashboard (React + Vite) `[DOCUMENTED PROCEDURE]`
```bash
# Run from repository root
cd frontend
npm run dev
```
*Verify: Open `http://127.0.0.1:5173` in your browser.*

### Browser Tab: Shopping & Extension Testing `[PENDING MANUAL BROWSER VALIDATION]`
1. In Brave/Chrome, ensure the extension is loaded from `<repo-root>/extension` via `brave://extensions`.
2. Visit `https://www.amazon.in/dp/B0H297XH3K`.
3. Open the Review Master popup, click **Extract Smartphone Data**, and inspect results.

---

## 8. Master Command Reference Table

| Component | Goal | Command | Working Directory | Verification Status | Expected Result |
|---|---|---|---|:---:|---|
| **Extension** | Run tests | `npm test` | `extension/` | `[TERMINAL-TESTED]` | 52 passing tests (0 failed) |
| **Extension** | Check permissions | `npm run check-permissions` | `extension/` | `[TERMINAL-TESTED]` | Permission gate verified (MV3) |
| **Extension** | Build check | `npm run build` | `extension/` | `[TERMINAL-TESTED]` | Extension ready for unpacking |
| **Frontend** | Install packages | `npm ci` | `frontend/` | `[TERMINAL-TESTED]` | 297 packages installed cleanly from lockfile |
| **Frontend** | Run tests | `npm test` | `frontend/` | `[TERMINAL-TESTED]` | 10 test suites passed, 65 tests passed (Vitest) |
| **Frontend** | Run ESLint | `npm run lint` | `frontend/` | `[TERMINAL-TESTED]` | ESLint 9 scan passed (0 errors) |
| **Frontend** | Typecheck | `npm run typecheck` | `frontend/` | `[TERMINAL-TESTED]` | Zero TypeScript errors (`tsc --noEmit`) |
| **Frontend** | Start dev server | `npm run dev` | `frontend/` | `[TERMINAL-TESTED]` | Listening on `http://localhost:5173` (200 OK) |
| **Frontend** | Build bundle | `npm run build` | `frontend/` | `[TERMINAL-TESTED]` | Production bundle generated in `dist/` |
| **Backend** | Evaluate env | Check `env_genai` version | `backend/` | `[DOCUMENTED PROCEDURE]` | Verify Python 3.12 compatibility |
| **Backend** | Start API | `uvicorn app.main:app --host 127.0.0.1 --reload` | `backend/` | `[FUTURE STAGE]` | Listening on `http://127.0.0.1:8000` |
| **Backend** | Run tests | `pytest tests/` | `backend/` | `[FUTURE STAGE]` | Unit test suite passing |
| **Backend** | Lint code | `ruff check .` | `backend/` | `[FUTURE STAGE]` | Clean lint report |
| **Database** | Start datastores | `docker compose up -d postgres redis` | Repo Root | `[DOCUMENTED PROCEDURE]` | Containers healthy |
| **Database** | Run migrations | `docker compose run --rm migrate` | Repo Root | `[FUTURE STAGE]` | Database schema at head |
| **Database** | Stop services | `docker compose down` | Repo Root | `[DOCUMENTED PROCEDURE]` | Containers stopped safely (data preserved) |

---

## 9. Troubleshooting & FAQ

### Q1: `ModuleNotFoundError: No module named 'pydantic'` when running pytest
- **Cause:** Running `pytest` using the host's system Python (e.g. Python 3.10) rather than the approved Python 3.12 virtual environment.
- **Solution:** Activate the approved Python 3.12 environment first, then re-run `pytest tests/`.

### Q2: Port 5173 is already in use
- **Cause:** Another instance of Vite or another local web server is occupying the port.
- **Solution:** Identify the process with `lsof -i :5173` or `ss -tulpn | grep 5173`, inspect the PID, and gracefully terminate only that specific process with `kill <PID>`. Alternatively, start Vite on another port: `npm run dev -- --port 5174`.

### Q3: Extension popup says "Unsupported URL"
- **Cause:** The active tab is not an Amazon India URL.
- **Solution:** Navigate to `https://www.amazon.in/` (specifically a product detail page containing `/dp/` or `/gp/product/`).

### Q4: Extension returns "Needs Review: Product Not Found"
- **Cause:** The page is a search result, category browse page, or non-product page missing `#productTitle`.
- **Solution:** Open an individual smartphone product listing.

### Q5: Docker Compose `migrate` service fails
- **Cause:** In Phase 1, Alembic database migrations have not yet been written.
- **Solution:** Start only essential datastores without migrations: `docker compose up -d postgres redis`.

---

## 10. Safe Shutdown Procedures

To cleanly shut down your local development environment:

```bash
# 1. Stop Frontend: Press Ctrl+C in Terminal 3
# 2. Stop Backend: Press Ctrl+C in Terminal 2
# 3. Stop Containers: In Terminal 1 (from repository root), run:
docker compose down

# 4. Optional: Clean local caches
rm -rf frontend/dist backend/.pytest_cache backend/.ruff_cache
```
