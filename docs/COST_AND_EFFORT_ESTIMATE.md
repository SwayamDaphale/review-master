# Cost and Effort Estimate (rough order of magnitude)

**Read this first.** These are planning estimates built from the user-story counts and stated assumptions. Accuracy is roughly **±40%** and should be re-estimated at the end of Phase 0 (after the spikes and the open decisions are resolved). Infrastructure prices are indicative ranges, not quotes: verify with the chosen provider's pricing calculator. People cost is not priced here because salaries and rates depend on the organization.

---

## 1. Team assumption

| Role | Allocation | Notes |
|---|---|---|
| Tech lead / architect | 1 (counted in the 5 below) | Reviews, ADRs, hard problems |
| Backend engineers | 2 | Catalog, evaluation, evidence, pricing, API |
| Frontend + extension engineer | 1 | React/Vite app, MV3 extension |
| AI engineer | 1 | Agents, extraction, grounding, prompt evals |
| QA / test automation | 0.5 | Golden dataset, Playwright, security tests |
| DevOps / platform | 0.5 | CI/CD, infra as code, observability, backups |
| UX / UI designer | 0.5 early, then 0.25 | Prototype screens first (capsule §48 step 1) |
| Product owner | 0.5 | Priorities, acceptance, pilot |
| Domain experts (smartphones, laptops, SSDs) | Part-time, from Phase 0 | **Critical path** for evaluation models |
| Legal / privacy advisor | On demand, early | Marketplace terms, privacy, extension policies |

Engineering throughput assumption: about 16 productive person-days per engineer per month (meetings, reviews, context switching excluded).

## 2. V1 effort

Basis: V1 has **41 user stories** (26 Must, 15 Should). One story ≈ design + build + tests + review + documentation.

| Component | Low (person-days) | High (person-days) | Basis |
|---|---|---|---|
| 41 V1 stories | 205 | 328 | 5–8 person-days per story |
| Platform foundations (repo, CI/CD, auth, tenancy/RLS, observability, base data layer, adapter framework) | 60 | 90 | Shared work not attributable to one story |
| Hardening and launch (security tests, load test, backup drill, pilot support, bug fixing) | 30 | 50 | |
| **Total engineering** | **295** | **468** | |
| Contingency | +20% | +20% | Unknowns: marketplace data access, extension review |
| **Total with contingency** | **≈ 354** | **≈ 562** | |

With 5 engineers at ~80 person-days per month combined: **≈ 4.4 to 7 months to a pilot-ready V1.** Delivery plan (`DELIVERY_PLAN.md`) uses 13 two-week sprints (~6 months) plus a 2-sprint pilot.

Not included in engineering days: domain-expert time to define and calibrate models, evidence acquisition (expert testing, licensed data), legal review, and design time beyond the allocation above.

## 3. V2 and V3 (indicative only)

| Release | Scope | Estimate |
|---|---|---|
| V2 | 8 stories (chat with tools, buy/track/wait, second adapter, mobile, purchase verification, brand pilot, commercial API, RAG), plus enabling infra (gateway, SSO, observability) | ≈ 200–350 engineering person-days (mobile app is the largest swing) → ~2.5–4.5 months with the same team |
| V3 / vision | Context graph, predictive price, household mode, new domains | Not estimated: re-plan after V2 learnings and pilot data |

## 4. Infrastructure running cost (monthly, indicative, USD)

Assumes a small pilot on managed cloud services; excludes LLM usage (§5) and data licensing (§6). **Replace with calculator output** once the provider (open decision #4) is chosen.

| Item | Production pilot | Staging | Notes |
|---|---|---|---|
| Application compute (API ×2, worker ×2, beat, gateway) | 80–250 | 40–100 | Small containers; autoscaling later |
| Managed PostgreSQL (HA, PITR backups) | 100–300 | 30–80 | Largest fixed item |
| Managed Redis | 15–60 | 10–20 | |
| Object storage + versioning + replication | 5–40 | 2–10 | Grows with evidence volume |
| Load balancer, CDN, WAF, DNS | 20–80 | 10–30 | |
| Observability (hosted Sentry/Grafana or self-hosted) | 0–150 | 0–30 | Free tiers may suffice early |
| Email/push provider | 0–30 | 0–5 | Volume dependent |
| Backup/DR extras (cross-region copies, drills) | 10–40 | — | |
| CI/CD (GitHub Actions minutes, registry) | 0–50 | — | Shared across environments |
| **Indicative total** | **≈ 230–1,000** | **≈ 90–280** | Excluding LLM and data licences |

Local-LLM option: running Ollama-class models for extraction/classification needs a GPU or a large CPU host. It converts per-token cost into fixed hosting cost; decide based on volume and data-privacy needs.

## 5. LLM usage cost model

Formula: `monthly_cost = requests_per_day × 30 × (1 − cache_hit_rate) × tokens_per_request × price_per_token`.

Illustration only: **average 3,000 tokens per LLM-backed request** (input + output) and an **illustrative blended price of $1 per million tokens**. Replace the price with your provider's current blended rate; real prices differ widely by model, and routing cheap tasks to a local model lowers it.

| LLM-backed requests/day | Cache hit 70% | Cache hit 50% |
|---|---|---|
| 1,000 | ≈ $27 / month (27M tokens) | ≈ $45 / month (45M tokens) |
| 10,000 | ≈ $270 / month | ≈ $450 / month |
| 100,000 | ≈ $2,700 / month | ≈ $4,500 / month |

Levers already in the design: explanation caching (most page views cost zero LLM calls), batch feedback summarization, model routing (local vs cloud), per-request and per-tenant budgets at the gateway, template fallbacks on budget breach.

## 6. Costs that can dominate and are not estimated

| Item | Why it matters |
|---|---|
| **Marketplace data access / licensing** | Official APIs, licensed feeds or authorized providers may carry fees. This could exceed all infrastructure cost and shapes feasibility. Decide with legal and product early |
| **Evidence acquisition** | Expert testing, lab data and licensed benchmarks cost per product. Without tier-1 evidence most products show Limited confidence |
| Domain experts | Model definition, calibration, expert reviews |
| Security review / penetration test | Recommended before commercial launch |
| Legal and privacy advice | Marketplace terms, privacy law, terms of use |
| Software licences and seats | Source hosting, error tracking, design tools, store developer accounts |
| Support and operations after launch | On-call, moderation, expert coordination |

## 7. What would change the estimate

- Marketplace without a usable official/licensed data source → larger adapter effort or a different V1 marketplace.
- Expert workflow moved from V2 into V1 → add roughly the effort of stories US-029 to US-032 (4 stories ≈ 20–32 person-days) plus portal UX.
- Native mobile in V2 vs cross-platform → large swing.
- Team smaller than 5 engineers → timeline scales roughly inversely.
- Compliance requirements (certifications, data residency) → additional platform work.

## 8. Assumptions to confirm with the tech lead

1. Team size and skills (FastAPI, React/Vite, MV3 extensions, LangGraph, PostgreSQL RLS).
2. V1 scope remains: one marketplace, three categories, extension + responsive web, deterministic evaluation.
3. Expert workflow timing (V1 vs V2).
4. Cloud/provider and production runtime.
5. Who owns domain-expert engagement and evidence acquisition.
