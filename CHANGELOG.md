# Changelog

## 2026-10-12 — merge into a single project

**Merged sources**
- `review-master-complete-package.zip` (base) — 59 files.
- `review-master-architecture.zip` — compared file by file: a strict subset of the complete package (12 files; only `README.md` and the architecture document differed, and the complete package has the newer versions). Nothing was lost; it is superseded.
- `Review_Master_User_Stories_By_Priority.xlsx` — checked against the story set: same 53 stories, identical content (acceptance criteria and test conditions are the same text, stored as one paragraph instead of bullet lines). Kept unchanged in `requirements/` as an alternative view next to the role-grouped workbook.

**Added**
- `docs/TRACEABILITY_MATRIX.md` and `requirements/Review_Master_Traceability.xlsx`: every story mapped to backend module, architecture section, API endpoints, tables, agents/skills, phase, flow and test approach. All references were validated against the documents.
- `CHANGELOG.md`, README stubs in `backend/`, `frontend/`, `extension/`.

**Changed (found while mapping stories)**
- `docs/api/openapi.yaml`: 54 → 64 operations, 61 → 69 schemas (user/role admin, evaluation-model list/get/create, evidence versions, webhook delete/deliveries/replay).
- `docs/ARCHITECTURE_VIEWS.md`: added the `user_space/` module (saved products, preferences, notification settings) to the backend layout.
- `README.md` and `docs/00_INDEX.md`: rewritten/extended for the single-project structure.

**Open findings** — see `docs/TRACEABILITY_MATRIX.md` (G1 to G6); the main one is that no story covers sign-up/login/MFA.
