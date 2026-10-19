# Evaluation Model Specifications

How category evaluation models are defined, reviewed, calibrated and published. This is the **biggest open item** in the plan: the engineering (engine, registry, versioning, confidence) is designed, but the *content* of each model (weights, thresholds, evidence requirements) needs domain experts. The capsule states the example parameters are "starting design examples, not final production weights" and that final parameters and weights "must be validated before publication."

Draft files (parameter lists taken from the capsule, everything else marked `proposed` or `null`):
- `evaluation-models/smartphone_v1.draft.yaml` (7 quality parameters + `value` signal)
- `evaluation-models/laptop_v1.draft.yaml` (8 + `value`)
- `evaluation-models/external_ssd_v1.draft.yaml` (7 + `value`)

> Numbers in these files are intentionally **not invented**. Weights and thresholds are `null` so a draft can never be published by accident: the publish endpoint rejects any model with a null weight/threshold or weights that do not sum to 1.0.

---

## 1. What a model contains (capsule §16)

| Section | Content | Where decided |
|---|---|---|
| Parameters | Key, name, definition | Domain expert |
| Weights | Share of the quality score per parameter (sum 1.0) | Domain expert, validated by sensitivity analysis |
| Normalization / scoring rule | `linear_range`, `piecewise`, `ordinal` or `boolean` with thresholds | Domain expert |
| Inputs | Normalized spec fields and evidence the parameter reads | Domain expert + engineering |
| Evidence requirements | Minimum trust tier to score, preferred source, maximum age | Domain expert |
| Critical flag | If a critical parameter is not scored, confidence is capped at Limited | Domain expert |
| Confidence policy | Component weights, tier factors, bands, freshness half-lives, tier-1 share for High | Engineering + domain expert |
| Version and status | `draft → review → published → retired`; immutable after publish | Process (below) |

## 2. The `value` parameter

All three capsule parameter lists end with `value`, while the capsule's rules require quality to be separate from price. Proposed resolution (needs your confirmation, architecture §12 #2):
- `value` is a **derived signal** computed at read time from the quality score and the current/median offer price.
- It is **not** part of the stored evaluation and does not change the overall quality score.
- Rationale: a stored evaluation would otherwise change whenever prices move, breaking auditability and caching.

In the draft files `value` appears under `derived_signals` with `excluded_from_quality_score: true`.

## 3. Scoring rule types

| Type | Use for | Example (illustrative shape only) |
|---|---|---|
| `linear_range` | Continuous measured values | Map `[min, max]` of sustained write MB/s to 0–100, clamped |
| `piecewise` | Non-linear value curves | Capacity bands, brightness bands |
| `ordinal` | Ordered categories | IP rating ladder, update-years ladder |
| `boolean` | Feature present or not | NFC present |

All rules are pure functions of the normalized value. A missing value yields `NOT_SCORED`, never 0.

## 4. Publication process

```
 draft ──► review ──► published ──► retired
   │         │
   │         └─ domain expert + engineering approval recorded (who, when)
   └─ edit freely; no user-visible effect
```

Publish checklist (also embedded in each draft file):
1. All weights set; sum is exactly 1.0.
2. All thresholds set, each with a written rationale.
3. Evidence requirements and maximum ages set per parameter.
4. Critical parameters confirmed by a domain expert.
5. Calibrated against the manually reviewed test set (§5).
6. Sensitivity analysis done (§6).
7. Golden evaluation fixtures added to CI.
8. Explicit approval recorded; `approved_by`, `published_at` stored; the version becomes immutable.

Changing anything after publication means a **new version**. Existing evaluations keep the old version label; re-evaluation inserts new rows under the new version.

## 5. Calibration against a reviewed test set

The capsule requires a manually reviewed V1 test dataset. Proposed use for models:
1. Domain experts choose a representative set of products per category (spread across price tiers and brands). **Set size to be agreed**; do not publish a number before a baseline exists.
2. For each product, experts record an independent ranking/judgement *before* seeing model output.
3. Run the draft model; compare the ordering (rank correlation) and inspect every disagreement.
4. Adjust thresholds and weights; record why. Re-run. Freeze the set as golden fixtures.

## 6. Sensitivity analysis

For each model, vary each weight (for example ±20% relative) and check how rankings and `high/limited/insufficient` bands move. A model whose top-N order flips under small weight changes is not ready: report it to the domain experts instead of choosing weights that hide the instability.

## 7. Expected V1 behaviour (set expectations early)

Most V1 evidence will be tier 2 (manufacturer/marketplace). With the tier-1 share rule for High confidence, many products will honestly show **Limited confidence** until expert or independent test evidence exists. That is correct behaviour. Plan an evidence-acquisition track (expert testing, licensed test data) in parallel with engineering, otherwise the product will look uniformly "limited" at launch.

## 8. Responsibilities

| Task | Owner | Reviewer |
|---|---|---|
| Parameter definitions, weights, thresholds, critical flags | Domain expert(s) | Product owner |
| Model schema, registry, validation, engine | Backend engineers | Tech lead |
| Golden fixtures, determinism tests | QA / backend | Domain expert |
| Publish approval | Domain expert + engineering | Admin records approval in the audit log |
