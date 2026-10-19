# ADR-0011: S3-compatible object storage; SeaweedFS locally; MinIO not used

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Evidence files need durable storage with versioning and signed URLs. A 2026 check found MinIO's community repository archived (April 2026) after community Docker images stopped (October 2025).

## Decision
Code talks the S3 API through `S3_ENDPOINT_URL`. Local/CI use SeaweedFS; production uses AWS S3, Cloudflare R2 or GCS with versioning and replication. SeaweedFS flags to be verified when pinning.

## Consequences
No lock-in and no dependency on an archived project. Local object store runs without auth (dev only).

## Alternatives considered
MinIO (rejected: archived); Garage/RustFS (viable alternatives); storing files in PostgreSQL (rejected: size and backup impact).
