# Changelog

## 2026-11-12 — Phase B10: Product Comparison & Requirement-Based Recommendation Engine

- **Database Migration `0012_b10_comparison_recommendations`**:
  - Created `recommendations` table for persistent audit storage of recommendation runs, parsed requirements, ranked items, excluded candidates, and SHA-256 invariant fingerprints.
  - Attached PostgreSQL trigger `trg_comparison_sessions_max_active` executing `enforce_max_active_comparison_sessions()` using `pg_advisory_xact_lock` to strictly enforce the maximum of 2 active comparison sessions per user even under high-concurrency race conditions.
- **Product Comparison Engine (`app.services.comparison_service`, `app.repositories.comparison_repository`)**:
  - Full comparison session lifecycle: create, retrieve, list, add/remove variants, and explicit archiving.
  - Category-locked comparison matrix supporting up to 5 variants per session, rejecting cross-category items and duplicate additions.
  - Honest missing data representation: genuine boolean `False` is distinctly preserved, and absent attributes are flagged with `is_missing=True`.
  - Strict dimension separation: overall evaluation score, confidence state, coverage, commercial offers/pricing, and community sentiment signals remain fully decoupled.
  - Intelligent evaluation reuse (`app.services.evaluation_cache`): cache fingerprint verification against variant configuration and evidence snapshot hashes, with fast Redis caching and transparent PostgreSQL fallback.
- **Requirement-Based Recommendation Engine (`app.services.requirement_parser`, `app.services.constraint_engine`, `app.services.ranking_service`, `app.services.recommendation_service`)**:
  - Requirement parsing: structured extraction of budget, physical constraints, soft preferences, unit normalizations, and brand exclusions via Groq LLM with deterministic regex fallback.
  - Three-valued constraint engine (`PASS`, `FAIL`, `UNKNOWN`): candidates with missing specifications or failing hard constraints are strictly excluded from ranking with human-readable audit reasons.
  - Deterministic recommendation ranking: multi-tier stable tie-breaking prioritizing overall evaluation score, confidence state, coverage, price, and variant UUID.
  - Evidence-grounded template explanations referencing verified specifications and model versions without hallucinated claims.
  - SHA-256 invariant input and output fingerprints stored alongside recommendation records and logged to `audit_logs`.
- **REST APIs & Frontend Integration**:
  - REST endpoints under `/api/v1/comparisons` (session lifecycle and matrix computation) and `/api/v1/recommendations` (query parsing, recommendation generation, and historical retrieval).
  - React frontend integration: interactive `ComparePage.tsx`, requirement-driven `RecommendationsPage.tsx`, updated TanStack Query endpoints in `httpClient.ts`, navigation links in `Layouts.tsx`, and routes in `App.tsx`.
- **Testing & Verification**:
  - Comprehensive automated test suite `tests/test_b10_comparison_recommendation.py` passing 9/9 tests including parallel database-level concurrency tests with 6 simultaneous threads.
  - Full backend regression verification: Alembic (`test_alembic.py`), B9 (`test_b9_evaluation_engine.py`), B8 (`test_b8_identity_resolution.py`), B7 (`test_b7_background_processing.py`), and B6 (`test_b6_extraction_ingestion.py`) passing 100%.
  - Frontend verification: 75/75 Vitest tests passing; production TypeScript build (`tsc --noEmit && vite build`) passing with zero errors.

## 2026-11-11 — Phase B9: Deterministic Evaluation Engine

- **Database Migrations `0010_eval_engine_b9` & `0011_eval_db_immutability`**:
  - `0010_eval_engine_b9`: Added model metadata and lifecycle columns to `evaluation_models` (`description`, `status`, `active_version_id`, `created_by`), cryptographic `configuration_hash` to `evaluation_model_versions`, execution trace fields to `evaluations` (`configuration_hash`, `input_fingerprint`, `output_fingerprint`, `calculation_policy_version`), and audit columns to `parameter_results` (`effective_weight`, `evidence_version_ids`, `raw_input_value`, `normalized_value`, `scoring_rule`).
  - `0011_eval_db_immutability`: Attached `trg_parameter_results_append_only` to `parameter_results` to reject all direct updates and deletions; attached `trg_eval_model_version_immutability` to `evaluation_model_versions` enforcing draft mutability, published immutability (except status-only deprecation), and permanent deprecated immutability at the PostgreSQL engine level.
- **Deterministic Non-LLM Scoring Engine (`app.services.evaluation_rules`)**:
  - Implemented pure Decimal arithmetic scoring functions conforming strictly to ADR-0003: `linear_range` (higher/lower is better), `piecewise` (monotonic linear interpolation), `boolean` (explicit false handling; missing never false), and `ordinal` (strict domain key mapping).
  - Guaranteed missing attribute values remain explicitly `missing` and never default to zero or fabricate scores.
- **Deterministic Evaluation Calculator (`app.services.evaluation_calculator`)**:
  - Dynamic weight normalization across evaluated parameters summing to 1.00000.
  - Coverage calculation with configurable floor (default 0.40); withholds overall score if floor is not met.
  - Evidence-aware confidence scoring based on trust tiers (T1-T4), verification states, and contradiction penalties (-0.15 for unresolved conflicts).
  - Reproducible SHA-256 canonical fingerprints for input data and output evaluation results.
- **Model Registry & Immutability (`app.services.evaluation_registry`)**:
  - Managed model lifecycle: `draft -> validated -> published -> deprecated`.
  - Strictly enforced published model version immutability (mutations or duplicate publications rejected).
  - Maintained category-level active version pointers and append-only recalculation history.
- **REST APIs & Celery Background Processing**:
  - REST endpoints under `/api/v1/evaluation-models` and `/api/v1/variants/{id}/evaluations` with RBAC enforcement (`EVALUATION_MANAGE`, `EVALUATION_READ`).
  - Durable Celery tasks `evaluation.calculate` and `evaluation.recalculate` tracking Job lifecycle transitions.
- **Verification & Acceptance**:
  - 14 golden fixtures in `tests/fixtures/evaluations/` verified with byte-for-byte exact hash and score reproduction.
  - 26/26 tests passing in `tests/test_b9_evaluation_engine.py` across Groups A through I.
  - Zero regressions across Alembic, Foundation, B6, B7, and B8 test suites.

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
