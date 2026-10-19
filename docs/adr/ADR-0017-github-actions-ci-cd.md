# ADR-0017: GitHub Actions for CI/CD with a determinism gate

- **Status:** Assumed
- **Date:** 2026-10-10

## Context
A CI/CD platform is required (user requirement); the choice is not yet confirmed (open decision #6).

## Decision
Pipeline: lint/types → tests → golden determinism gate → migration gate → OpenAPI check → frontend/extension build + permission gate → security scans → image build → compose smoke test → staging → manual approval → production.

## Consequences
Quality gates enforce the architecture's key promises. Pin actions to commit SHAs before production. If another platform is chosen the stages translate directly.

## Alternatives considered
GitLab CI, Jenkins, Azure DevOps (equivalent stages).
