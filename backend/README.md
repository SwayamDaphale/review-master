# backend

FastAPI modular monolith plus Celery workers. **No code yet.** Start from the planned layout in `../docs/ARCHITECTURE_VIEWS.md` §3.1 and the contract in `../docs/api/openapi.yaml`.

Must provide for the infrastructure to run: `GET /healthz`, `app.main:app`, `app.worker.celery_app`, Alembic migrations (`alembic upgrade head`), pytest marker `golden`, `app.tools.export_openapi`, `requirements.txt` and `requirements-dev.txt`.

Where to look first: data model `../docs/DATA_MODEL.md` · rules `../docs/REVIEW_MASTER_ARCHITECTURE_README.md` §3 · skills `../docs/SKILLS.md` · agents `../docs/AGENTS.md` · stories mapped to modules `../docs/TRACEABILITY_MATRIX.md`.
