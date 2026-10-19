# ADR-0003: The evaluation engine is deterministic; the LLM is never the scoring authority

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Capsule rule 1 and the product's trust promise. Scores must be reproducible, explainable and auditable.

## Decision
Scores come from a pure function of canonical variant, validated specs, eligible evidence and a published model version. LLMs only extract, parse, summarize and explain, and every generated text is grounding-validated. A CI determinism gate enforces byte-identical results for golden fixtures.

## Consequences
Reproducibility and auditability. Cost: models (weights, thresholds) must be authored by humans; explanations must be constrained to stored data.

## Alternatives considered
LLM-as-judge scoring (rejected: non-deterministic, unauditable, injectable).
