# ADR-0016: Docker Compose with profiles for optional services

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
The reference project runs everything in one compose file; Review Master has many optional components (gateway, SSO, graph, scanning, observability).

## Decision
Nine core services run by default; optional services sit behind profiles (`rag`, `local-llm`, `llm-gateway`, `enterprise-auth`, `graph`, `scan`, `observability`, `tools`). Compose is for development and CI; production uses managed data services with the same application images.

## Consequences
Light default stack, clear opt-in. Compose is not a production orchestrator. The stack was syntax-checked but not started in the authoring environment: validate and pin images in Phase 0.

## Alternatives considered
One monolithic compose file (rejected: heavy), Kubernetes locally (rejected: unnecessary).
