# Review Master — Backend Service

Review Master core backend service built with Python 3.12, FastAPI, SQLAlchemy 2.0, and Pydantic Settings.

---

## 1. Prerequisites

- **Python:** Version `3.12.x` (pinned for CI, Docker, and local development).
- **Node.js & npm:** Node.js `v20.x`+ / `v24.x` and npm `10.x`+ (for frontend and extension tooling).
- **Database:** PostgreSQL 16 (local installation or via `compose.yml`).
- **Cache:** Redis 7 (optional for slice 1, configured in `compose.yml`).

---

## 2. Windows PowerShell Setup (Primary Development Workflow)

### Step 1: Create the Virtual Environment
From the repository root, create the dedicated `mr_env` virtual environment using Python 3.12:

```powershell
py -3.12 -m venv backend\mr_env
```
*(Run this from the repository root only if `backend\mr_env` does not already exist).*

### Step 2: Environment Activation / Direct Invocation
To activate the virtual environment in PowerShell:

```powershell
.\backend\mr_env\Scripts\Activate.ps1
```

> **Note on PowerShell Execution Policy:** If script execution is restricted on your machine, **do not weaken system-wide security policies**. You can invoke the environment's Python executable directly for all commands:
>
> ```powershell
> .\backend\mr_env\Scripts\python.exe <arguments>
> ```

### Step 3: Install Dependencies
Install runtime and development dependencies inside `mr_env`:

```powershell
.\backend\mr_env\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

### Step 4: Configure Local Environment Variables
Create your local `.env` from the safe template:

```powershell
Copy-Item .env.example .env
```

Open `.env` in your editor and configure your local settings. By default, local development uses:
- `APP_ENV=development`
- `DEBUG=true`
- `LOG_LEVEL=info`
- `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/reviewmaster`
- `JWT_SECRET=dev-only-local-secret-change-in-production`
- `API_KEY_PEPPER=dev-only-local-pepper-change-in-production`

*(Never commit `.env` to Git. Real secrets must remain strictly local).*

### Step 5: Run Linting and Type Checking

```powershell
.\backend\mr_env\Scripts\ruff.exe check backend\app backend\tests
.\backend\mr_env\Scripts\ruff.exe format --check backend\app backend\tests
.\backend\mr_env\Scripts\mypy.exe backend\app
```

### Step 6: Run Backend Tests

```powershell
.\backend\mr_env\Scripts\python.exe -m pytest backend\tests
```

---

## 3. Linux / macOS Setup

For Linux or macOS development environments:

```bash
# 1. Create virtual environment
python3.12 -m venv backend/mr_env

# 2. Activate environment
source backend/mr_env/bin/activate

# 3. Install dependencies
pip install -r backend/requirements-dev.txt

# 4. Copy environment template
cp .env.example .env

# 5. Run tests
pytest backend/tests
```

---

## 4. Cross-Laptop Setup Guide (Setting Up on a Second Laptop)

To reproduce this environment on a secondary laptop, **never copy the `mr_env` directory between machines**. Virtual environments contain machine-specific absolute symlinks and binaries.

Follow this exact procedure on the new machine:

1. **Clone or Pull the Repository:**
   ```powershell
   git clone https://github.com/SwayamDaphale/review-master.git
   cd review-master
   ```
2. **Verify Python 3.12 Runtime:**
   ```powershell
   py -3.12 --version
   ```
   *(Ensure Python 3.12.x is installed from python.org if missing)*.
3. **Recreate `mr_env`:**
   ```powershell
   py -3.12 -m venv backend\mr_env
   ```
4. **Install Dependencies from Committed Manifest:**
   ```powershell
   .\backend\mr_env\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
   ```
5. **Create Local `.env` Configuration:**
   ```powershell
   Copy-Item .env.example .env
   ```
   Provide machine-specific credentials or development database passwords in `.env`.
6. **Configure Database & Run Migrations:**
   Start PostgreSQL (locally or via `docker compose up -d postgres`) and apply migrations:
   ```powershell
   .\backend\mr_env\Scripts\alembic.exe upgrade head
   ```
7. **Run Tests & Verify Service Health:**
   ```powershell
   .\backend\mr_env\Scripts\python.exe -m pytest backend\tests
   ```

---

## 5. Security & Secret Protection Rules

- **Zero Secrets in Git:** `.env` and `backend/mr_env/` are explicitly ignored by `.gitignore`.
- **Deliberate Path Resolution:** `app.core.config.Settings` dynamically resolves `.env` relative to the repository root, ensuring consistent behavior regardless of working directory.
- **Log Sanitization:** `Settings.safe_summary()` and `safe_database_url()` redact passwords, authorization headers, and provider keys so secrets are never output to logs or terminal consoles.
- **No Client Exposure:** Backend provider keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`, etc.) are read strictly server-side and never exposed to the frontend web app or browser extension.
