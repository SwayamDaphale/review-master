# ADR-0001: Start as a modular monolith

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
The capsule (§13, §42) requires a focused V1 and warns against premature microservices. The team is small and the domain boundaries are still being learned.

## Decision
One deployable FastAPI application organized as modules (catalog, evaluation, evidence, community, expert, recommendation, pricing, notifications, ai, admin) with enforced import rules. Workers run the same codebase. Extract services only on a real trigger (independent scaling, availability, deployment cycle, isolation, team ownership).

## Consequences
Faster delivery, simpler debugging and transactions, one deployment. Requires discipline: import-linter rules in CI and per-module table ownership so extraction stays cheap. Extraction path documented in ARCHITECTURE_VIEWS §5.

## Alternatives considered
Microservices from day one (rejected: operational cost, distributed transactions, slower learning); serverless functions (rejected: poor fit for long jobs and shared domain model).
