# ADR-0004: Evaluation models are versioned and immutable once published

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Historical evaluations must remain auditable (capsule rules 7 and 18). Weights are not final and will change.

## Decision
Model versions move draft → review → published → retired. Published versions are immutable; every evaluation stores `model_version_id` and an `evidence_snapshot_hash`. Evaluations are append-only; recalculation inserts new rows.

## Consequences
Full history and safe iteration. Storage grows with every recalculation; keep rows compact and index by `(variant_id, created_at desc)`.

## Alternatives considered
In-place updates of scores (rejected: breaks auditability).
