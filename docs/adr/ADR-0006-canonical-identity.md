# ADR-0006: Canonical identity is separate from listings and offers; LLM output can never confirm a match

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Capsule rules 4 and §11. A wrong variant makes a correct evaluation misleading.

## Decision
Hierarchy Family → Product → Variant → Listing → Offer. Deterministic matching order with states confirmed/probable/ambiguous/unmatched. Attributes with `source = llm` can never produce `confirmed`; ambiguity goes to user choice and the admin queue.

## Consequences
Safer identification and an audit trail for mappings. Cost: an admin review queue and a labeled set to measure accuracy.

## Alternatives considered
URL-based identity (rejected: unstable); LLM auto-merge (rejected: silent errors).
