# ADR-0010: Route all LLM traffic through a gateway (LiteLLM)

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Provider choice is open, keys must not spread across services, and cost must be capped per tenant.

## Decision
The backend calls one OpenAI-compatible endpoint. LiteLLM holds provider keys, aliases (`rm-fast`, `rm-strong`, `rm-embed`), retries, fallbacks and per-key budgets. Local Ollama is the no-key default for development.

## Consequences
Provider swap without code changes; central cost control. One more service to run and secure; the gateway becomes a critical dependency with a circuit breaker and template fallback.

## Alternatives considered
Direct provider SDKs in the code (rejected: key sprawl, lock-in).
