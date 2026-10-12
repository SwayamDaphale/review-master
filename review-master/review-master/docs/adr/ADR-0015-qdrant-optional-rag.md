# ADR-0015: Qdrant for RAG, optional; pgvector as the lean alternative

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
RAG is a V2 capability (capsule §28, rule 14: vector DB is optional and retrieval-focused); the reference project already uses Qdrant.

## Decision
Qdrant behind the `rag` compose profile and feature flag. Retrieval filters on approval state and tenant, returns empty when nothing passes the threshold, and never feeds scoring. A store-agnostic retrieval skill allows pgvector for small corpora.

## Consequences
No cost or complexity until needed. Two retrieval options to maintain only if both are used.

## Alternatives considered
Always-on vector DB in V1 (rejected: no V1 requirement).
