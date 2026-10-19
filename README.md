# Review Master — single project

One repository that holds everything for Review Master: requirements, architecture and planning documents, implementation guides, the story-to-architecture traceability map, infrastructure definitions, and the (still empty) code folders. Start with **`docs/00_INDEX.md`** for the reading order, **`IMPLEMENTATION_AND_WORKING.md`** for how the system works end-to-end, or **`docs/EXECUTIVE_SUMMARY.md`** for a one-page brief.

## How the pieces map together

```
 requirements/  ──►  docs/TRACEABILITY_MATRIX.md  ──►  docs/ (architecture, API, data, tests, plan)  ──►  code + infra
 capsule, stories     53 stories -> modules,            architecture, agents, skills, data model,         backend/ frontend/ extension/
 (docx, xlsx)         endpoints, tables, phases         OpenAPI, security, NFR, cost, delivery plan        compose.yml, CI/CD, Dockerfiles
```

| You want to know | Open |
|---|---|
| **How the system works & implementation** | `IMPLEMENTATION_AND_WORKING.md` |
| What are we building and why | `docs/EXECUTIVE_SUMMARY.md`, `requirements/Review_Master_Master_Project_Capsule.md` |
| Which user stories exist, by role or by priority | `requirements/Review_Master_User_Stories.xlsx` (by version, then role, then priority), `requirements/Review_Master_User_Stories_By_Priority.xlsx` (by version, then priority), `requirements/Review_Master_User_Stories.docx` (template format) |
| Where each story is implemented | `docs/TRACEABILITY_MATRIX.md` and `requirements/Review_Master_Traceability.xlsx` |
| How the system works | `docs/REVIEW_MASTER_ARCHITECTURE_README.md`, `docs/ARCHITECTURE_VIEWS.md`, `docs/SEQUENCE_DIAGRAMS.md`, `docs/CLIENTS_EVENTS_RELIABILITY.md` |
| What the AI may and may not do | `docs/AGENTS.md`, `docs/SKILLS.md` |
| Data and API | `docs/DATA_MODEL.md`, `docs/api/openapi.yaml` |
| Quality, security, tests | `docs/NON_FUNCTIONAL_REQUIREMENTS.md`, `docs/TEST_STRATEGY.md`, `docs/SECURITY_THREAT_MODEL.md` |
| Models (weights, thresholds) | `docs/EVALUATION_MODEL_SPECS.md`, `docs/evaluation-models/` |
| Cost, timeline, risks | `docs/COST_AND_EFFORT_ESTIMATE.md`, `docs/DELIVERY_PLAN.md` |
| Why we decided X | `docs/adr/` |
| Run it | `compose.yml`, `.env.example`, `Makefile` |

## Layout

```
review-master/
├── README.md  CHANGELOG.md
├── requirements/   capsule, 3 user-story files, traceability workbook
├── docs/           00_INDEX, executive summary, architecture set, API, data model, plan, ADRs, diagrams
├── backend/        README + Dockerfile (code to be written)
├── frontend/       README + Dockerfile (code to be written)
├── extension/      README (code to be written)
├── docker/         Postgres init SQL, LiteLLM gateway config, Prometheus config
├── .github/        CI/CD workflow, PR template, Dependabot
├── compose.yml  .env.example  Makefile  .gitignore  .pre-commit-config.yaml
```

## Quick start (once the code folders contain code)

```bash
cp .env.example .env        # set JWT_SECRET and API_KEY_PEPPER
make up                     # core stack (docker compose up -d --build)
make local-llm              # optional: local models      make rag     # optional: Qdrant
make help                   # all targets
```

Local URLs: API http://localhost:8000 · Web http://localhost:5173 · Mailpit http://localhost:8025 · Object store (S3) http://localhost:8333.

## Known gaps (stated plainly)

- **No application code yet.** Compose and CI are YAML-validated but never started; verify and pin image tags in Phase 0.
- **Evaluation models are drafts** (null weights and thresholds) and need domain experts.
- **The story set has no sign-up/login stories** (finding G1 in the traceability matrix); add them.
- **Estimates are rough (±40%)**; infrastructure prices are indicative.
- **Open decisions** (V1 marketplace, cloud, LLM provider, expert workflow timing, `value` signal, billing, SEO, data residency): architecture §12 and `docs/DELIVERY_PLAN.md` §4.
- Privacy/legal items in `docs/SECURITY_THREAT_MODEL.md` §5 are questions for counsel, not advice.
