# Changelog

## 2026-11-11 — Phase B8: Identity Resolution, Variant Matching & Evidence Quality Management

- **Database Migration `0009_identity_and_evidence_quality`**:
  - Created `external_identity_mappings` for authoritative ASIN/external ID mapping.
  - Created `identity_review_queue` for ambiguous and low-confidence match triage.
  - Created `evidence_conflicts` for tracking contradictory attribute observations non-destructively.
  - Created `evidence_verification_history` for append-only audit trail of verification status changes.
- **5-Stage Identity Resolution Pipeline**:
  - Stage 1: Exact marketplace ID mapping check (`ExternalIdentityMapping`).
  - Stage 2: Trusted listing mapping check (`MarketplaceListing`).
  - Stage 3: Deterministic product and variant fingerprinting (`FingerprintService`).
  - Stage 4: Multi-candidate scoring with contradiction penalties.
  - Stage 5: Ambiguity detection and `IdentityReviewQueue` dispatch.
- **Evidence Quality & Provenance**:
  - Enforced backend-controlled trust tiers (T1-T4) rejecting client-submitted trust overrides.
  - Implemented non-destructive conflict preservation and resolution workflows.
  - Implemented verification state lifecycle tracking with audit reason logging.
- **Background Tasks & REST APIs**:
  - Added Celery tasks `identity.resolve`, `identity.review_candidates`, `evidence.assign_trust`, `evidence.detect_conflicts`.
  - Added REST APIs under `/api/v1/identity` and `/api/v1/evidence`.
- **Testing & Verification**:
  - Automated test suite `tests/test_b8_identity_resolution.py` passing 22/22 tests across Categories A through K.
  - Full regression pass confirmed with B1-B7 test suites.

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
