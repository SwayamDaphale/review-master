# ADR-0007: Evidence trust tier is fixed at ingestion

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Manufacturer claims must never look like independent tests (capsule rule 6); trust must not depend on query-time guesses.

## Decision
Tier 1 independent/expert-tested, tier 2 manufacturer/marketplace/other authorized, tier 3 community, derived from `source_type` at insert. Confidence uses tier factors and a tier-1 share requirement for High confidence.

## Consequences
Honest labelling. In V1 many products will show Limited confidence until tier-1 evidence exists; an evidence-acquisition plan is needed.

## Alternatives considered
Content-based trust inference at query time (rejected: unstable and manipulable).
