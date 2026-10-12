# ADR-0005: Treat `value` as a separate, price-dependent signal

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
The capsule lists `value` among example parameters but also requires quality to be separate from price (rule 2). Storing a price-dependent number in an evaluation would make evaluations change with every price move.

## Decision
`value` is computed at read time from the quality score and current/median offer price and is not part of the stored overall quality score. Awaiting confirmation (architecture §12 #2).

## Consequences
Clean separation, stable cached evaluations. The UI must present value next to, not inside, the quality score.

## Alternatives considered
Include value in the overall score (rejected: violates separation and caching).
