# Review Master — Documentation Index

Start here. Reading order for a technical reviewer, then a coverage check against the capsule's own list of 35 expected architecture outputs (capsule §52).

## Reading order

| # | Document | Purpose | Time |
|---|---|---|---|
| 1 | [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) | One page: what, why, decisions, plan, risks, likely questions | 5 min |
| 2 | [REVIEW_MASTER_ARCHITECTURE_README.md](REVIEW_MASTER_ARCHITECTURE_README.md) | Main architecture: rules, components, decision rules, tech mapping, limitations, open decisions | 30 min |
| 3 | [ARCHITECTURE_VIEWS.md](ARCHITECTURE_VIEWS.md) | Context, container, component, deployment views; monolith → services path; observability | 15 min |
| 4 | [SEQUENCE_DIAGRAMS.md](SEQUENCE_DIAGRAMS.md) | Six key flows step by step | 10 min |
| 5 | [AGENTS.md](AGENTS.md) and [SKILLS.md](SKILLS.md) | AI agent contracts; deterministic skills catalog | 20 min |
| 6 | [DATA_MODEL.md](DATA_MODEL.md) and [api/openapi.yaml](api/openapi.yaml) | Schema and API contract skeleton | 20 min |
| 7 | [CLIENTS_EVENTS_RELIABILITY.md](CLIENTS_EVENTS_RELIABILITY.md) | Extension, web, mobile; events/webhooks; jobs; failure and retry | 15 min |
| 8 | [EVALUATION_MODEL_SPECS.md](EVALUATION_MODEL_SPECS.md) and [evaluation-models/](evaluation-models/) | How models are defined and published; three draft models | 10 min |
| 9 | [NON_FUNCTIONAL_REQUIREMENTS.md](NON_FUNCTIONAL_REQUIREMENTS.md), [TEST_STRATEGY.md](TEST_STRATEGY.md), [SECURITY_THREAT_MODEL.md](SECURITY_THREAT_MODEL.md) | Quality attributes, testing, security and privacy | 25 min |
| 10 | [COST_AND_EFFORT_ESTIMATE.md](COST_AND_EFFORT_ESTIMATE.md), [DELIVERY_PLAN.md](DELIVERY_PLAN.md) | Estimate, phases, milestones, decisions, risks | 15 min |
| 11 | [adr/](adr/README.md) | 17 architecture decision records | 10 min |
| 12 | [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md) | Every user story mapped to module, endpoints, tables, agents/skills, phase and tests; gaps found | 10 min |

Requirements the architecture traces back to: `../requirements/` (Master Project Capsule; user stories as Word, Excel grouped by role, and Excel by priority; traceability workbook).
Runnable infrastructure: `../compose.yml`, `../.env.example`, `../.github/workflows/ci.yml`, `../Makefile`.

## Coverage of the capsule's expected outputs (§52)

| # | Expected output | Where |
|---|---|---|
| 1 | System architecture | Architecture §2–3; `diagrams/architecture_overview.png` |
| 2 | Context diagram | ARCHITECTURE_VIEWS §1 |
| 3 | Container diagram | ARCHITECTURE_VIEWS §2 |
| 4 | Component diagram | ARCHITECTURE_VIEWS §3 |
| 5 | V1 modular-monolith architecture | ARCHITECTURE_VIEWS §3; ADR-0001 |
| 6 | Future service-extraction architecture | ARCHITECTURE_VIEWS §5 |
| 7 | Product/entity data model | DATA_MODEL §1.2; Architecture §3.4 |
| 8 | ER diagram | Architecture §6; DATA_MODEL §2 |
| 9 | Marketplace adapter architecture | Architecture §3.4 |
| 10 | Evaluation-engine architecture | Architecture §3.7; SKILLS (Evaluation); EVALUATION_MODEL_SPECS |
| 11 | Evidence/provenance architecture | Architecture §3.6; DATA_MODEL §1.4 |
| 12 | Review-intelligence architecture | Architecture §3.8; AGENTS §5; SKILLS (Feedback) |
| 13 | Expert verification workflow | Architecture §3.9; SEQUENCE_DIAGRAMS §4 |
| 14 | Recommendation architecture | Architecture §3.10; SEQUENCE_DIAGRAMS §3 |
| 15 | AI/LLM orchestration | Architecture §3.3, §3.13; AGENTS |
| 16 | RAG architecture | Architecture §3.14; ADR-0015 |
| 17 | Browser extension architecture | CLIENTS_EVENTS_RELIABILITY §1 |
| 18 | Web architecture | CLIENTS_EVENTS_RELIABILITY §2 |
| 19 | Mobile architecture | CLIENTS_EVENTS_RELIABILITY §3 |
| 20 | API architecture | Architecture §3.2; `api/openapi.yaml` |
| 21 | Event/webhook architecture | CLIENTS_EVENTS_RELIABILITY §4 |
| 22 | Authentication/RBAC architecture | Architecture §3.16; SECURITY_THREAT_MODEL §2; SEQUENCE_DIAGRAMS §5 |
| 23 | Security architecture | SECURITY_THREAT_MODEL; Architecture §8 |
| 24 | Deployment architecture | ARCHITECTURE_VIEWS §4; `compose.yml`; Architecture §7 |
| 25 | Observability architecture | ARCHITECTURE_VIEWS §6 |
| 26 | Database schema | DATA_MODEL |
| 27 | API contracts | `api/openapi.yaml` (skeleton: 64 operations, 69 schemas) |
| 28 | Technology rationale | Architecture §5; ADRs |
| 29 | Scalability plan | NON_FUNCTIONAL_REQUIREMENTS §4; ARCHITECTURE_VIEWS §5 |
| 30 | Failure/retry strategy | CLIENTS_EVENTS_RELIABILITY §6 |
| 31 | Testing architecture | TEST_STRATEGY |
| 32 | CI/CD | Architecture §7; `.github/workflows/ci.yml` |
| 33 | LLM cost-control strategy | Architecture §4; COST_AND_EFFORT_ESTIMATE §5 |
| 34 | Modular monolith → services migration path | ARCHITECTURE_VIEWS §5 |
| 35 | Architecture Decision Records | `adr/` |

All 35 are covered. Depth varies: items 26 and 27 are design-stage skeletons to be replaced by generated artifacts once code exists.

## Status of each artifact

| Artifact | Status |
|---|---|
| Architecture, agents, skills, views, sequences, data model, NFRs, tests, security, plan, ADRs | Design baseline, ready for review |
| `api/openapi.yaml` | Skeleton; refs and IDs checked, not a running API |
| `evaluation-models/*.yaml` | **Drafts with null weights/thresholds** — need domain experts |
| `compose.yml`, Dockerfiles, CI workflow | Written; YAML-validated; **not yet run** — Phase 0 exit criterion |
| Cost and effort | Rough estimate, ±40%, assumptions stated |
| Application code | Not started |
