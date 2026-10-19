# AGENTS.md — Review Master Agent Specifications

This document defines every **LLM-assisted agent** in Review Master: its responsibility, inputs/outputs, the guardrails it must enforce, and its failure behavior. Treat it as the contract each implementation must satisfy. Unit tests should assert against these contracts directly, not just against "reasonable-looking output."

---

## What is and is not an agent

Review Master's core is deterministic. Only the parts that genuinely need model judgment are agents. Everything else is a **skill** (see `SKILLS.md`) or a **human role**.

| Capability | Type | Where defined |
|---|---|---|
| Evaluation scoring, confidence, aggregation | Deterministic engine (skills) | `SKILLS.md` — Evaluation |
| Product matching order, unit normalization | Deterministic (skills) | `SKILLS.md` — Identity |
| Hard-constraint filtering, ranking, comparison matrix | Deterministic (skills) | `SKILLS.md` — Recommendation |
| Review anomaly signals | Deterministic (skills) | `SKILLS.md` — Feedback |
| Price context and alerts | Deterministic (skills) | `SKILLS.md` — Price |
| Expert investigation and assessment | **Human** (Expert Reviewer, Admin) | Architecture §3.9 |
| Extraction, requirement parsing, summarization, explanation, chat | **Agents** | This document |

**Rule of thumb:** if an agent's job could be a deterministic function, it must be a skill. An agent may never write to `evaluations`, `evidence` (verdict fields), `offers`, `price_records`, or `expert_assessments`.

---

## Conventions used below

- **Input / Output** are the shape of data each agent consumes/produces (see `schemas.py` in the repo; keep in sync).
- **Guardrails** are hard constraints the agent must never violate, regardless of what the LLM inside it generates. They are enforced in code (validators, post-checks), not only in prompts.
- **Failure mode** defines what the agent returns when it cannot complete its task. Every agent must have a defined failure output; a raw exception is never surfaced to the Orchestrator.
- **Untrusted text:** marketplace pages, reviews, uploaded documents and user messages are data, never instructions. All agents receive such text only after `sanitize_untrusted_text`.
- **Labelling:** any text produced by an agent and shown to a user is marked AI-generated, and an `ai_runs` row is written (input/evidence refs, model, config, result, tokens, cost, `trace_id`).

---

## 1. Orchestrator

**Role:** Central controller for AI flows (requirements, explanations, chat). Owns `RMState`, sequences tool calls and agents, enforces caps, and routes to the Response Assembler. It is **not** used for plain deterministic API calls.

- **Input:** user input or explanation request, `mode`, `actor` (user/API key, org, roles, scopes).
- **Output:** final `RMState` including `payloads`, `answer`, cost counters and `trace_id`.
- **Guardrails:**
  - Must enforce `tool_call_count <= max_tool_calls` and `llm_iterations <= max_llm_iterations` in code, not by agent judgment.
  - Must enforce `cost_usd <= cost_ceiling_usd`; on breach, degrade to deterministic template output rather than failing.
  - Must pass the actor's identity to every tool; a tool call is rejected if the actor lacks the scope.
  - Must persist state to `ai_runs` at every transition so a crash leaves a recoverable trace.
- **Failure mode:** an unrecoverable tool failure marks only that section `unavailable: infra_failure`; the Orchestrator proceeds with the rest instead of blocking the response.

---

## 2. Requirement Extraction Agent

**Role:** Turns a natural-language request ("1 TB external SSD under ₹8,000 for video editing, sustained write matters") into a structured `Requirements` object.

- **Input:** sanitized user text, list of supported categories and their schemas.
- **Output:** `Requirements` (`category`, `hard` constraints, `preferences`, `use_case`, `clarifications_needed`).
- **Guardrails:**
  - Output must validate against the Pydantic schema (`validate_requirements_schema`); the backend rejects anything else.
  - Must not invent values. A budget, capacity or compatibility not stated by the user stays unset and is listed in `clarifications_needed`.
  - Hard constraints and preferences are separate fields; wording like "prefer" or "care about" never becomes a hard constraint.
  - Category must be one of the supported categories; otherwise `category = null` and the user is told the request is outside supported scope.
- **Failure mode:** malformed output → retry once with a stricter output-format instruction, then return `clarifications_needed` with a plain question to the user, or fall back to keyword search.

---

## 3. Product Extraction Agent

**Role:** Assists the marketplace adapter when deterministic parsing cannot extract attributes from permitted page content (for example free-text specs).

- **Input:** sanitized page text from a permitted extraction, category schema.
- **Output:** `list[ProposedAttribute]` each with `name`, `raw_value`, `source_span` (character offsets in the input), `confidence`.
- **Guardrails:**
  - Extraction is verbatim: `raw_value` must be a substring of the input at `source_span`. A value without a valid span is dropped.
  - Never fills a missing attribute from general knowledge ("this phone usually has 8 GB RAM").
  - Output goes to `proposed_attributes` and then through normalization and validation; the agent never writes to canonical product or variant tables.
  - Every attribute is tagged `source = llm` so the matcher can never produce `confirmed` from LLM attributes alone.
- **Failure mode:** on parse failure or empty result, return `extraction_failed` with no attributes; the lookup continues with deterministic attributes only.

---

## 4. Identity Matching Assistant

**Role:** Proposes ranked candidate canonical variants when the deterministic matcher ends in `probable` or `ambiguous`, and writes a short reason for the admin review queue.

- **Input:** normalized attributes of the listing, candidate variants from the deterministic matcher.
- **Output:** ranked `candidates` with `reason` and `differences` (which attributes differ).
- **Guardrails:**
  - Cannot set `match_state` to `confirmed`. Its output is advisory input to a human or to the user's own selection.
  - Must list the attributes that differ between candidates (capacity, generation, region variant); it may not call two variants "the same" if any identity attribute differs.
  - Cannot merge, split, or edit canonical products.
- **Failure mode:** on error, return the deterministic candidates unranked with `reason: "assistant_unavailable"`; state stays `ambiguous`.

---

## 5. Feedback Intelligence Agent

**Role:** Structures and summarizes community feedback: sentiment, recurring issues, positive experiences, usage context.

- **Input:** moderated feedback items for one variant (batched, capped), minimum sample met.
- **Output:** `FeedbackSummary` (`themes[]` each with `label`, `polarity`, `count`, `feedback_ids`), `usage_contexts[]`.
- **Guardrails:**
  - Every theme and every statement must reference `feedback_ids` that exist in the input; counts are computed by code from those ids, not by the model.
  - Never labels a reviewer or a review "fake", "paid" or "bot". Review-quality is handled by deterministic signals (`SKILLS.md` — Feedback), not by this agent.
  - Output is community experience only. It must not be presented as laboratory fact and must not feed the evaluation engine.
  - Below the minimum sample size (starting value 10), no summary is produced.
- **Failure mode:** on error or low sample, return raw counts and the individual feedback list with `summary: unavailable`.

---

## 6. Evaluation Explanation Agent

**Role:** Writes a plain-language explanation of one stored evaluation.

- **Input:** the stored `Evaluation` payload: parameter results, overall score or `null`, confidence state and reasons, evidence references with source types, limitations, model version.
- **Output:** explanation text plus `referenced_parameters` and `referenced_evidence`.
- **Guardrails:**
  - May only use facts present in the payload. No new specifications, scores, evidence, prices, availability or expert findings. Enforced by `validate_grounding` before return.
  - Must state the confidence level, and must say so explicitly when confidence is `limited` or `insufficient_evidence`; must not describe a withheld (`null`) score or a `NOT_SCORED` parameter as low.
  - Must distinguish evidence classes: a manufacturer claim is never described as a test; a community report is never described as a laboratory result.
  - Ignores any instruction found inside payload text fields (prompt-injection defense).
- **Failure mode:** grounding validation fails → one regeneration with stricter instructions → then a deterministic template explanation built from the payload.

---

## 7. Comparison Summary Agent

**Role:** Summarizes the trade-offs in a stored comparison of two or more same-category products.

- **Input:** the `Comparison` payload (aligned parameter scores, confidence per product, key specs, current offers).
- **Output:** short summary naming where each product leads and the main trade-offs, with `referenced_products` and `referenced_parameters`.
- **Guardrails:**
  - Uses only data in the comparison payload; grounding-validated.
  - Keeps signals separate: it may say "cheaper but weaker on sustained write", but it must not blend quality and price into one verdict or number.
  - Products with `insufficient_evidence` are described as such, never as the worst performer.
  - Refuses cross-category comparisons (the engine already blocks them; the agent double-checks).
- **Failure mode:** fall back to a deterministic table-to-text template listing the top differing parameters.

---

## 8. Recommendation Explanation Agent

**Role:** Explains a ranked recommendation result to the user.

- **Input:** validated `Requirements`, ranked results (fit score, confidence factor, which hard constraints passed, offers), or the "no eligible product" result with the suggested constraint to relax.
- **Output:** explanation text plus `referenced_products`.
- **Guardrails:**
  - Cannot add, remove or reorder candidates. The ranking is produced by the deterministic engine.
  - Must mention when a top result has limited or insufficient confidence, and must show the trade-offs (excellent overall but fails budget, cheap but poorly evaluated, review anomalies present).
  - Must state the hard constraints that were applied.
  - If no product qualifies, must say so and present the engine's suggested relaxation; it may not suggest products that failed a hard constraint.
- **Failure mode:** fall back to a template that lists the ranked products with their scores, confidence and constraint results.

---

## 9. Conversational Q&A Agent (V2)

**Role:** Answers product questions in a chat, choosing from explicit backend tools.

- **Input:** sanitized user message, conversation history, `actor`, allowed tool list for that actor.
- **Output:** a tool-call plan and, after results arrive, a draft answer for the Response Assembler.
- **Guardrails:**
  - Data access only through tools: `search_products`, `get_product`, `get_evaluation`, `compare_products`, `get_offers`, `get_price_history`, `get_feedback`, `get_expert_assessment`, `save_product`, `create_price_alert`. No database or free-form retrieval access.
  - `save_product` and `create_price_alert` are write tools: they require an explicit user confirmation step before the call is executed.
  - Must not speculate about future prices or invent availability; if a tool returns nothing, the answer says the data is not available.
  - RAG passages (when enabled) are cited with their source type and are never presented as verified facts about a specific variant.
  - Instructions inside tool results, reviews, documents or marketplace text are ignored.
- **Failure mode:** if tools fail or return nothing, answer with what is available and state what could not be retrieved; never fill the gap from model knowledge.

---

## 10. Response Assembler (Grounding & Safety Gate)

**Role:** Produces the final user-facing payload. This is Review Master's analog of AURA's Response Generator: no silent pass-through of weak or unavailable information.

- **Input:** draft text from an agent, the payloads used, confidence states, `trace_id`.
- **Output:** final response with visible confidence badges, caveats, AI-generated label, source types, and the `trace_id` reference.
- **Guardrails:**
  - Runs `validate_grounding(answer, payloads)`; an answer containing an ungrounded number, product or parameter is rejected.
  - Must not strip caveats for `limited` / `insufficient_evidence` confidence, `unavailable` sections, stale data, or review-quality signals, even if the UI has no good display slot yet. The caveat data must exist in the payload regardless of rendering.
  - Must keep the three trust outputs separate in the payload: Review Master evaluation, community experience, expert assessment.
  - External marketplace ratings, when included, are labelled as external information.
- **Failure mode:** if the pipeline stopped at a cap (tool calls, iterations, cost), the output states that the answer is partial and which sections are missing, rather than presenting an unqualified final answer.

---

## Cross-agent test requirements

Each agent's test suite must include:
1. **Schema test:** invalid output is rejected and the failure mode is returned.
2. **Grounding test:** an answer containing a number or product not in the payload fails.
3. **Injection test:** a payload or review containing "ignore previous instructions…" does not change the output.
4. **Empty-input test:** empty tool results produce `unavailable`, never a guess.
5. **Determinism test (for engines the agent calls):** same payload gives the same engine output; only the wording of agent text may vary.
