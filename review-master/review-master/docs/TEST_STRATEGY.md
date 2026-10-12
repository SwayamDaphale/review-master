# Test Strategy and Testing Architecture

Based on capsule §44 (testing strategy), §47 (KPIs) and the CI gates in architecture §7. The capsule requires a **manually reviewed V1 test dataset** and warns not to invent accuracy numbers before a baseline exists. This document therefore defines *how* to measure, not target percentages.

---

## 1. Test pyramid

| Layer | Scope | Tooling | Runs |
|---|---|---|---|
| Unit | Skills and pure functions (normalization, matching order, scoring, confidence, ranking, anomaly detectors, grounding validator) | `pytest`, hypothesis (property tests for scoring/normalization) | Every commit |
| Golden / determinism | Evaluation engine with fixed fixtures; byte-identical output | `pytest -m golden` | Every commit (CI gate) |
| Integration | API + PostgreSQL + Redis, migrations, RLS, outbox, Celery tasks (eager or real worker) | `pytest` with service containers | Every commit |
| Contract | OpenAPI validity, response schema conformance, backward compatibility of `/api/v1` | OpenAPI validator, schema tests (e.g. Schemathesis) | Every commit |
| AI behaviour | Agent contracts: schema, grounding, injection, empty input (AGENTS.md "Cross-agent test requirements") | `pytest` with a stubbed/recorded LLM; a small live-model suite on schedule | Stub: every commit; live: nightly |
| Extension | Supported page, unsupported page, missing data, API failure, ambiguous identity; permission gate | Playwright with the unpacked extension against saved page fixtures | Every commit |
| Frontend | Components and key flows | Vitest + Testing Library; Playwright end-to-end | Every commit / nightly |
| Security | Authorization matrix, role escalation, private evidence, expert self-approval, malicious upload, tenant isolation | `pytest` + scripted abuse cases; dependency and image scans | Every commit / weekly |
| Performance | Load on lookup and evaluation endpoints | k6 or Locust | Before pilot; before each major release |
| Restore drill | Backup restore and integrity check | Scheduled job | Monthly |

## 2. Capsule test areas mapped to concrete suites

| Area | Cases (from capsule §44) |
|---|---|
| Identity | exact product; variant; generation; capacity; ambiguous listing; missing model number; same model opened by different URLs; LLM attribute conflicting with verified mapping |
| Evaluation | deterministic output; unit normalization (GB/TB, MB/s vs GB/s); missing data stays `NOT_SCORED`; conflicting evidence (tier rule, same-tier conflict); scoring version retained; critical parameter missing caps confidence; coverage below floor withholds overall score |
| Recommendation | hard constraints; budget; user preferences; no eligible product (+ relaxation suggestion); low-confidence top product flagged; deterministic ranking for same input |
| Extension | supported page; unsupported page; missing data; API failure; ambiguous identity |
| Security | unauthorized access; role escalation; private evidence access; expert self-approval; malicious uploads; cross-tenant read attempt; API key scope/expiry/revocation |
| AI | schema failure → retry → fallback; ungrounded number rejected; prompt-injection text ignored; empty tool result → `unavailable`; write tools need confirmation |

## 3. The golden dataset

Purpose: freeze known inputs and expected outputs so any scoring change is intentional.

- Location: `backend/tests/golden/` (fixtures as JSON/YAML: variant, validated specs, evidence, model version → expected evaluation).
- Created from the manually reviewed test set (see `EVALUATION_MODEL_SPECS.md` §5), reviewed by domain experts.
- CI rule: a changed expected output is only accepted together with a new model version or an explicit, reviewed fixture update.
- Includes edge fixtures: all evidence tier 2 (expect Limited), missing critical parameter, same-tier conflict, stale evidence, unit-conversion cases, a product with only 30% coverage (overall withheld).

## 4. Measuring product identification accuracy (KPI baseline)

The capsule lists identification accuracy as a KPI but gives no target. Method:

1. Build a labeled set: real listings from the V1 marketplace, each manually matched by a reviewer to the correct canonical variant or marked "no canonical match". Include the hard cases (same model different capacity, generation confusion, ambiguous titles).
2. Run the matcher; record `match_state` and the chosen variant per listing.
3. Report: share of listings correctly matched when `confirmed`/`probable`; share wrongly confirmed (the dangerous error); share routed to `ambiguous`/`unmatched`; share where review was needed.
4. Track the **user correction rate** in production as the live signal.
5. Do not set a target until the baseline exists; then agree targets with the product owner. The error that matters most is a wrong `confirmed`, so report it separately.

## 5. Other KPI baselines (from capsule §47)

| KPI | How it is measured |
|---|---|
| Evaluation response time | p50/p95 from API metrics |
| Recommendation acceptance | Share of recommendation sessions where the user saves/compares/clicks an offer (define the event list) |
| Confidence calibration | Compare confidence states with expert verdicts on the reviewed set; check that High is right more often than Limited |
| User correction rate | `product_corrections` per lookups |
| Community feedback quality | Moderation approve rate; share of feedback with structured fields filled |
| Decision time | Session-level time from first lookup to action (needs consented analytics) |
| Price-alert usefulness | Alerts followed by click-through or purchase intent events |
| Weekly active users, API usage/retention | Product analytics and `usage_events` |

## 6. CI gates (summary)

lint and types → unit → determinism (golden) → integration (migrations, RLS, outbox) → OpenAPI contract → frontend and extension builds → permission gate (manifest) → security scans → image build → compose smoke test. Details in `.github/workflows/ci.yml`.

## 7. Test data and environments

- Synthetic seed data for local and CI; never real user data outside production.
- Marketplace pages for extension tests are **saved fixtures**, not live scraping in CI.
- Staging uses anonymized or synthetic data only.
- LLM calls in CI use a stub/recorded provider; a small scheduled suite uses a real model to detect prompt regressions.

## 8. Definition of done (per user story)

Acceptance criteria and test conditions from the user stories are implemented as automated tests where practical; golden fixtures updated if scoring is touched; audit rows verified where the story mentions auditing; OpenAPI updated; security checks (permission, tenant) included; documentation updated.
