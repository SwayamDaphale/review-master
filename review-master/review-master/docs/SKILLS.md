# SKILLS.md — Review Master Reusable Skills & Tool Catalog

Skills are the discrete, reusable capabilities that engines, agents and API endpoints call into. Keeping them as separate, independently-testable units (rather than baking logic into prompts or controllers) is what lets the extension, web app, API and chat share one implementation of every rule instead of duplicating scoring or matching logic.

Each skill lists: what it does, what it must guarantee, and what it explicitly does *not* do (to keep skill boundaries clean). **Unless marked `[LLM]`, a skill is deterministic code and must be unit-testable without an LLM call.**

---

## Identity & Normalization Skills

### `normalize_specs(raw_attributes, category_schema)`
- **Does:** Maps raw attributes to the category schema, converts units, and returns validated specs with `source`, `source_type`, `observed_at`.
- **Guarantees:** Missing values are `null`, never `0`. An unrecognized unit is returned as `needs_review`, never guessed. Same input → same output.
- **Does not:** Fetch data, call an LLM, or decide which source wins on conflict (that is `resolve_evidence_conflict`).

### `convert_units(value, from_unit, to_unit)`
- **Does:** Converts using a controlled table (GB/TB, MB/s/GB/s, mAh/Wh, inches/cm, etc.).
- **Guarantees:** Refuses ambiguous conversions (for example GB vs GiB without a flag) rather than approximating silently; returns the original value and unit alongside the converted one.
- **Does not:** Infer a unit when none is given.

### `match_product(normalized_attributes, source)`
- **Does:** Runs the deterministic matching order: verified marketplace ID mapping → manufacturer model number/GTIN → generation → exact configuration → normalized-attribute similarity → human review. Returns `match_state` and candidates.
- **Guarantees:** Attributes with `source = llm` can never produce `confirmed`. Two variants that differ in any identity attribute (capacity, generation, region variant) are never merged. Ambiguity returns multiple candidates, never a silent best guess.
- **Does not:** Create or merge canonical products. Admin tools do that with an audit row.

### `resolve_variant(product_id, configuration)`
- **Does:** Returns the exact `variant_id` for a configuration (for example 16 GB / 512 GB) or `none`.
- **Guarantees:** Exact match on configuration attributes only.
- **Does not:** Pick the "closest" variant.

---

## Evidence & Provenance Skills

### `attach_trust_tier(evidence_input)`
- **Does:** Sets `trust_tier` (1 independent/expert-tested, 2 manufacturer/marketplace/other authorized, 3 community) from `source_type` at ingestion.
- **Guarantees:** The tier is looked up from the source type, never inferred from content at query time.
- **Does not:** Judge whether the evidence is correct.

### `compute_freshness(evidence, now)`
- **Does:** Returns a `0–1` freshness factor using exponential decay with a half-life per evidence type (configurable per category).
- **Guarantees:** Pure function of `observed_at`, `source_type` and `now`.
- **Does not:** Delete or hide old evidence; it only lowers its weight.

### `check_upload_safety(file)`
- **Does:** Validates type and size, calls the malware scanner, and returns `safe | rejected | quarantined` with a reason.
- **Guarantees:** Unscanned files never reach evidence storage or RAG ingestion; the scan result is logged.
- **Does not:** Extract or interpret file content.

### `classify_source_label(evidence)`
- **Does:** Returns the user-facing label (`Independent test`, `Expert test`, `Manufacturer claim`, `Marketplace listing`, `Community report`).
- **Guarantees:** A manufacturer or marketplace source can never receive an "independent test" label; a community source can never receive a "laboratory" label.

---

## Evaluation Skills

### `score_parameter(parameter_def, eligible_evidence)`
- **Does:** Applies the model's rule (`linear_range`, `piecewise`, `ordinal`, `boolean`) to the best eligible evidence and returns `0–100` or `NOT_SCORED`, plus `evidence_refs`.
- **Guarantees:** No eligible evidence → `NOT_SCORED`, never `0`. Output always lists the evidence used.
- **Does not:** Apply weights or decide confidence.

### `resolve_evidence_conflict(evidence_items, tolerance)`
- **Does:** Picks the governing evidence for one parameter: higher trust tier wins; same tier within tolerance → equal; same tier beyond tolerance → `conflicted`.
- **Guarantees:** Never averages conflicting values. `conflicted` uses the most recent *verified* evidence if one exists, otherwise returns `NOT_SCORED`.
- **Does not:** Remove or edit any evidence record.

### `renormalize_weights(parameter_results, base_weights)`
- **Does:** Recomputes weights over the parameters that were actually scored.
- **Guarantees:** Weights over the scored subset always sum to 1.0; `NOT_SCORED` parameters contribute nothing.

### `compute_confidence(parameter_results, evidence_used, model_policy)`
- **Does:** Computes `coverage`, `source_quality`, `verification`, `freshness`, `consistency`, the weighted `confidence_score`, applies the critical-parameter cap and the tier-1 share rule, and returns `high | limited | insufficient_evidence` with reasons.
- **Guarantees:** Pure function. Confidence is separate from the overall score (a high score can come with limited confidence). Coverage below the floor (starting value 0.40) always yields `insufficient_evidence`.
- **Does not:** Use an LLM.

### `aggregate_evaluation(parameter_results, weights, model_policy)`
- **Does:** Implements the ordered decision rules in Architecture §3.7 and returns the overall score (or `null`), confidence, limitations and `model_version`.
- **Guarantees:** **Pure function** — same inputs and same published model version always produce the same output. This is what makes evaluation testable without mocking an LLM, and it is the target of the CI determinism gate.
- **Does not:** Call an LLM, read prices, or read community sentiment.

### `compute_value_signal(quality_score, offer_prices, category_policy)`
- **Does:** Computes the separate, price-dependent `value` signal at read time from a quality score and current/median offer price.
- **Guarantees:** The result is never written into an `evaluations` row. Missing price → `null`.
- **Does not:** Change the evaluation or ranking inputs for quality.

---

## Feedback & Review-Quality Skills

### `detect_near_duplicates(feedback_items, jaccard_threshold)`
- **Does:** Finds clusters of near-identical text (MinHash/SimHash), default threshold 0.85, minimum cluster size 3.
- **Guarantees:** Returns clusters with `feedback_ids` and similarity; deterministic for a given input and seed.
- **Does not:** Label any reviewer or conclude fraud.

### `detect_review_bursts(timestamps, baseline_days, z_threshold, min_count)`
- **Does:** Flags unusual bursts against a trailing baseline (default 30 days, z > 3, minimum count).
- **Guarantees:** Returns no signal when the sample is below the minimum count.
- **Does not:** Distinguish a viral launch from manipulation — it reports a pattern only.

### `build_review_quality_signals(product_id)`
- **Does:** Combines duplicate, burst, repeated-pattern, inconsistent-product-reference and cluster detectors into `review_quality_signals[]` with `signal_type`, `strength`, `evidence_ids`.
- **Guarantees:** Signals are product-level and worded as indicators. Negativity, writing style and a single unusual review never create a signal. Reviewer-level output goes only to the admin moderation queue.
- **Does not:** Compute a "fake probability" for a person.

---

## Recommendation & Comparison Skills

### `validate_requirements_schema(raw_requirements, category_registry)` 
- **Does:** Validates the `Requirements` object from the Requirement Extraction Agent against the Pydantic schema and the category registry.
- **Guarantees:** Rejects unknown fields, unsupported categories, negative or non-numeric limits. Moves unresolved fields into `clarifications_needed`.

### `apply_hard_constraints(candidates, hard_constraints)`
- **Does:** Filters candidates by budget, capacity, compatibility and required features, and records which constraint removed each rejected product.
- **Guarantees:** A product failing any hard constraint is never returned, regardless of score. An empty result is valid and returns the rejection reasons.

### `rank_candidates(candidates, preferences, confidence_factors)`
- **Does:** Computes `fit = Σ(pref·score)/Σ(pref)` over scored, relevant parameters and ranks by `fit × confidence_factor`.
- **Guarantees:** Deterministic and tie-broken by a stable key; the confidence factor and fit are both returned so they can be shown.
- **Does not:** Use an LLM or reorder after the fact.

### `suggest_constraint_relaxation(rejected_with_reasons)`
- **Does:** Returns the single constraint whose relaxation would admit the most well-evaluated candidates, with the effect size.
- **Guarantees:** Suggests one specific change (for example "raise budget to ₹X"), never a vague message.

### `build_comparison_matrix(variant_ids)`
- **Does:** Aligns parameter scores, confidence, key specs and offers for same-category variants.
- **Guarantees:** Rejects cross-category input with a reason; keeps quality, confidence and price in separate fields; `NOT_SCORED` stays `NOT_SCORED`.

---

## Price & Offer Skills

### `record_price_observation(offer_id, price, currency, observed_at, source)`
- **Does:** Appends a `price_records` row with provenance and availability.
- **Guarantees:** Append-only; duplicate observations (same offer, price, timestamp) are ignored idempotently.

### `get_price_context(variant_id, windows)`
- **Does:** Returns min/median/max for the requested windows (default 30/90/180 days) plus `coverage_days`.
- **Guarantees:** Reports coverage so the UI can warn about sparse data; no forecast is returned.

### `evaluate_price_alert(alert, new_observation)`
- **Does:** Decides whether an alert fires (price drop, target price reached) and applies the cooldown (default 24 h).
- **Guarantees:** Does not fire repeatedly for oscillation around a target; includes price, source and timestamp in the alert payload.

### `buy_track_wait_guidance(price_context, user_context)` *(V2)*
- **Does:** Rule-based guidance from current price, history, coverage, urgency, budget, availability and verified sale information.
- **Guarantees:** Never states a future price as certain; low coverage yields a cautious `track` result with the reason.

---

## Retrieval Skills (RAG, V2)

### `semantic_search(query, top_k, min_similarity, filters)`
- **Does:** Embeds `query` through the gateway, searches Qdrant with mandatory filters (`approval_state = approved`, tenant `org_id`), and returns passages above `min_similarity`.
- **Guarantees:** Never pads to fill `top_k`; an empty result is valid. Each passage returns `doc_id`, `trust_tier`, `source_type`.
- **Does not:** Treat retrieved text as verified, and never feeds scoring.

### `apply_trust_weighting(passages)`
- **Does:** Attaches `trust_tier` from ingestion metadata.
- **Guarantees:** Tier is looked up, never inferred from passage content.

### `graph_lookup(entities, relation_type)` *(V3)*
- **Does:** Queries the context graph for relations between entities, preferences and evaluations.
- **Guarantees:** Returns `last_verified` on every edge.
- **Does not:** Resolve ambiguous entities.

---

## AI Safety & Routing Skills

### `sanitize_untrusted_text(text, origin)`
- **Does:** Strips control characters, marks the text as data (delimited, tagged with `origin`), truncates to a limit, and flags instruction-like patterns.
- **Guarantees:** Untrusted text is never concatenated into a system or instruction section of a prompt.
- **Does not:** Claim to make injection impossible; it is one layer alongside tool-only access and grounding validation.

### `validate_grounding(answer, payloads)`
- **Does:** Checks that every number, product name, parameter name and unit in the answer exists in the request's tool payloads.
- **Guarantees:** Any ungrounded item fails validation and returns the offending spans.
- **Does not:** Judge writing quality or whether an explanation is helpful.

### `route_model(task_type, size_hint)` 
- **Does:** Chooses the local model (extraction, classification, requirement parsing) or the cloud model (chat, long explanations) through the gateway.
- **Guarantees:** Routing decision is logged with the result so cost/quality trade-offs can be tuned later.

### `batch_items(items, agent_type, max_batch)`
- **Does:** Groups items into one structured-output call per agent type.
- **Guarantees:** Batch size is capped (default 10); overflow creates another batch, not a larger call.

### `cache_lookup(key)` / `cache_store(key, value, ttl)`
- **Does:** Redis cache for evaluations (`variant_id + model_version_id + evidence_snapshot_hash`) and explanations (`evaluation_id + language + prompt_version`).
- **Guarantees:** Entries are invalidated on `evaluation.created/updated`; a stale explanation is never served for a newer evaluation.

---

## Infrastructure / Cross-Cutting Skills

### `check_permission(actor, action, resource)`
- **Does:** Central RBAC + scope + tenant check used by endpoints and by every chat tool.
- **Guarantees:** Deny by default; a denial is audit-logged; an actor can never grant itself a role.

### `log_trace(trace_id, event, payload)`
- **Does:** Writes a structured audit/trace event to PostgreSQL.
- **Guarantees:** Failures to log are surfaced as warnings, never silently swallowed, since audit gaps defeat traceability.

### `emit_event(event_type, payload)` / `sign_webhook(payload, secret)`
- **Does:** Publishes events (`product.evaluated`, `price.changed`, `feedback.moderated`, `ai.evaluation.proposed`, …) and signs webhook deliveries (`t=<unix>,v1=<hmac>`).
- **Guarantees:** Each event has a unique `event_id`; deliveries retry with backoff; payloads follow the documented schema.

### `rate_limit_check(actor, endpoint)` / `meter_usage(actor, endpoint, units)`
- **Does:** Token-bucket limiting in Redis and asynchronous usage metering into `usage_events`.
- **Guarantees:** Limits are per `api_key_id` / `user_id` / IP; metering never blocks the request path.

### `generate_api_key(org_id, scopes, expires_at)` / `verify_api_key(raw_key)`
- **Does:** Creates a key of the form `rm_live_<prefix>_<secret>` and verifies it by prefix lookup plus constant-time HMAC comparison.
- **Guarantees:** The secret is shown once and only its HMAC (with a server-side pepper) is stored; revoked or expired keys always fail verification.

---

## Skill Boundaries — Rule of Thumb

If you are about to add logic to an agent prompt or a controller that could instead be a deterministic function, it belongs here as a skill. Skills are the parts of the system you can unit test without an LLM call; agents are the parts that genuinely need model judgment (extracting attributes from messy text, parsing a free-form request, summarizing feedback, writing explanations). Keeping that line clear is what keeps the Evaluation Engine fully deterministic and testable — and what keeps the LLM from ever becoming the scoring authority.
