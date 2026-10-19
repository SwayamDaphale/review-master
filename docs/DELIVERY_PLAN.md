# Delivery Plan, Milestones and Risk Register

Follows the capsule's recommended development sequence (§48) and the V1/V2/V3 scope (§36–38). Timeline assumes the team in `COST_AND_EFFORT_ESTIMATE.md` §1 and **two-week sprints**. Dates are relative (Sprint 1 = start); convert to calendar dates once the team and start date are fixed. Story IDs are from `requirements/Review_Master_User_Stories.xlsx`.

---

## 1. Timeline overview

```
Sprint:   1    2    3    4    5    6    7    8    9   10   11   12   13  | 14   15
Phase 0  ████
Phase 1       ██████████████
Phase 2                 ██████████████████
Phase 3                           ██████████████████████
Phase 4                                          ██████████████████
Phase 5                                                    ██████████████
Pilot                                                                    | ██████
```

~13 sprints (≈ 6 months) to a pilot-ready V1, then a 2-sprint pilot. Phases overlap on purpose: the evaluation engine and the experience layer can be built in parallel once the data model and APIs are fixed.

## 2. Phases

### Phase 0 — Alignment and foundations (Sprint 1)
Goal: remove the biggest unknowns and make the repo runnable.
- Close decisions #1 (V1 marketplace), #4 (cloud/runtime), #5 (LLM provider), #6 (CI/CD) — see §4.
- Legal/terms review of the V1 marketplace; confirm permitted data sources.
- Prototype key screens (capsule §48 step 1): Product Panel, Evaluation View, Comparison View, Recommendation Drawer, Universal Command.
- Repo skeleton: backend, frontend, extension; `docker compose up` works; CI green; Alembic baseline; OpenAPI skeleton served.
- Spikes: marketplace adapter feasibility; LLM attribute-extraction quality on real pages; RLS proof of concept; extension permission minimum.
- Assign domain experts for the three categories.

**Exit criteria:** decisions recorded as ADRs; compose stack starts from a clean clone; golden-test harness runs in CI; legal answer on data sources; estimate re-baselined.

### Phase 1 — Platform core and identity (Sprints 2–4)
Stories: US-033 users/roles/permissions · US-037 audit log · US-002 canonical product/variant resolution · US-003 correction · US-004 normalized specs · US-005 search · US-035 mapping admin · US-036 evidence storage/management · US-034 evaluation model registry (draft/publish).
Also: auth (signup/login/MFA/API keys), tenancy with RLS, marketplace adapter framework, event outbox, job framework.

**Exit criteria:** a listing from the V1 marketplace resolves to a variant (confirmed/probable/ambiguous/unmatched) with admin review queue; role and tenant tests pass; migrations pass the gate; audit rows verified.

### Phase 2 — Evaluation engine (Sprints 4–7)
Stories: US-008 deterministic evaluation · US-009 score and parameter scores · US-010 confidence · US-011 evidence and provenance · US-013 evaluation history · US-006 product page with separated trust outputs (API).
Also: first published model for **one** category (recommended: External SSD, the simplest spec set), then the other two; golden fixtures from the reviewed test set; Redis cache and invalidation.

**Exit criteria:** determinism gate green; same score from API, web and extension payloads; ≤ 2 s cached retrieval measured; at least one model approved by a domain expert and published; sensitivity analysis recorded.

### Phase 3 — Experience layer and AI at the edges (Sprints 6–10)
Stories: US-001 extension detection · US-007 save products · US-018 compare · US-020 alternatives · US-021 natural-language requirements · US-022 hard constraints · US-023 recommendations · US-024 preferences · US-012 evaluation explanation · US-019 comparison summary.
Also: web app screens, extension side panel, AI orchestrator, agents with grounding gate, gateway, LLM budgets.

**Exit criteria:** end-to-end flow works on the V1 marketplace; agent contract tests pass (schema, grounding, injection, empty input); AI text labelled; extension permission gate green; first usability review of "≤ 3 clicks" flows.

### Phase 4 — Community, offers, alerts, expert workflow (Sprints 9–12)
Stories: US-014 feedback · US-015 community insights · US-016 review-quality signals · US-017 moderation · US-025 offers · US-026 price history · US-027 price alerts · US-028 notification control · US-029 to US-032 expert workflow (if in V1; see decision #3) · US-038 integration monitoring.

**Exit criteria:** moderation queue works; alerts fire once per cooldown; price history shows coverage; expert state machine enforced (no self-approval, COI block); integration health dashboard live.

### Phase 5 — API, hardening and pilot readiness (Sprints 11–13)
Stories: US-040 versioned APIs · US-041 signed webhooks · US-039 commercial separation guarantees.
Also: security test suite, penetration test (recommended), load test, backup restore drill, runbooks, dashboards and alerts, privacy/terms pages, extension store submission, pilot onboarding.

**Exit criteria:** security checklist (SECURITY_THREAT_MODEL §4) complete; restore drill passed; load-test results recorded; KPI instrumentation in place; pilot group and success measures agreed.

### Pilot (Sprints 14–15)
Small group; measure identification accuracy (labeled set + user correction rate), evaluation response time, recommendation acceptance, confidence calibration, decision time, price-alert usefulness (capsule §47). Fix, then decide V2 scope from data.

### After V1
- **V2:** US-042 chat with tools · US-043 buy/track/wait · US-044 second marketplace adapter · US-045 mobile · US-046 purchase verification · US-047 brand pilot · US-048 commercial API · US-049 RAG. Infra: `llm-gateway`, `rag`, `enterprise-auth`, `observability` profiles to production.
- **V3:** US-050 to US-053 (context graph, predictive price, household mode, new domains) — plan after V2 learnings.

## 3. Milestones

| ID | Milestone | Target | Evidence |
|---|---|---|---|
| M0 | Foundations ready | End Sprint 1 | Compose runs from clean clone, CI green, decisions recorded |
| M1 | Catalog + identity | End Sprint 4 | Listing → variant demo with admin queue |
| M2 | Evaluation engine | End Sprint 7 | Published model, golden tests, ≤ 2 s cached |
| M3 | Experience complete (internal) | End Sprint 10 | Extension + web + recommendations demo |
| M4 | Feature complete | End Sprint 12 | Community, offers, alerts, expert workflow |
| M5 | Pilot ready | End Sprint 13 | Security, restore, load, runbooks done |
| M6 | Pilot review | End Sprint 15 | KPI baseline report and V2 decision |

## 4. Decisions needed and by when

| # | Decision | Needed by | Blocks |
|---|---|---|---|
| 1 | V1 marketplace and permitted data sources | Sprint 1 | Adapter, offers, legal review |
| 2 | `value` as separate derived signal | Sprint 2 | Model schema, API |
| 3 | Expert workflow in V1 or V2 | Sprint 3 | Phase 4 scope and estimate |
| 4 | Cloud provider and production runtime | Sprint 2 | IaC, deployment, cost |
| 5 | LLM and embedding providers | Sprint 3 | Gateway config, cost model |
| 6 | CI/CD platform (GitHub Actions assumed) | Sprint 1 | Pipeline |
| 7 | Billing/payments provider (commercial API) | Before V2 | Plans, metering |
| 8 | Public SEO pages | Before V2 | Web architecture |
| 9 | Data residency and privacy regime | Sprint 2 | Hosting region, retention |
| 10 | Tier-1 share default for High confidence | Sprint 6 | Model calibration |

## 5. Dependencies and critical path

Critical path: **V1 marketplace decision → data access/legal → adapter → identity accuracy → evidence → evaluation models (domain experts) → pilot.** Engineering can build the engine against synthetic fixtures meanwhile, but a pilot cannot start without real marketplace data and approved models.

## 6. Working agreements

- Two-week sprints with demo; definition of ready (acceptance criteria and test conditions from the story) and definition of done (TEST_STRATEGY §8).
- Architecture changes go through ADRs (`adr/`).
- Evaluation model changes only through the publish process (EVALUATION_MODEL_SPECS §4).
- Scope gate: anything outside V1 scope (capsule §46) needs a recorded decision before work starts.

## 7. Risk register

Likelihood (L) and impact (I): H/M/L.

| # | Risk | L | I | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Marketplace terms or access block the planned data extraction | H | H | Early legal review; prefer official APIs/licensed feeds; choose the V1 marketplace by data access | Product + Legal |
| R2 | Domain experts unavailable, so models stay draft | M | H | Assign in Phase 0; start with one category; keep models as data so iteration is cheap | Product owner |
| R3 | Product identification accuracy too low | M | H | Reviewed labeled set, deterministic matching order, `probable` badge, admin queue, correction loop | Tech lead |
| R4 | Evidence scarcity → almost everything "Limited confidence" | H | M | Evidence acquisition plan (expert tests, licensed data); set expectations; show confidence transparently | Product owner |
| R5 | LLM extraction/explanation errors | M | M | Grounding gate, schema validation, deterministic fallbacks, injection tests | AI engineer |
| R6 | Scope creep from the long-term vision | H | M | V1 scope gate; extensibility through interfaces only | Tech lead |
| R7 | Extension store review delays or permission rejection | M | M | Minimal permissions, early submission, clear justifications | Frontend/extension |
| R8 | Adapter breaks when marketplace layout changes | H | M | Fixtures, health monitoring, official APIs, fast-fix runbook | Backend |
| R9 | LLM cost overrun | M | M | Caching, routing, budgets, template fallback | AI engineer |
| R10 | Skill gaps (LangGraph, MV3, RLS) | M | M | Spikes in Phase 0, pairing, ADRs | Tech lead |
| R11 | Security incident or tenant data leak | L | H | RLS + tests, security review, least privilege, incident runbook | Tech lead |
| R12 | Compose/infra never validated end-to-end | M | L | Phase 0 exit criterion; pin image tags | DevOps |
| R13 | Review manipulation undermines community data | M | M | Signals, moderation, verified-purchase states where possible | Backend |
| R14 | Commercial pressure to alter scores | L | H | Architecture rule (no write path), audit, written policy, disclosure labels | Product owner |
| R15 | Cost or timeline underestimated | M | M | Re-baseline after Phase 0; track velocity; contingency included | Tech lead |
