# ADR-0018: Groq as Primary Cloud Inference Provider; NVIDIA NIM as Backup Provider

- **Status:** Accepted
- **Date:** 2026-11-08

## Context
Phase B5 introduces AI review intelligence into Review Master, including aspect extraction, sentiment analysis, pros/cons extraction, and review clustering.

Previous architecture documents (ADR-0010) deferred external cloud inference providers in favor of local Ollama deployments or a gateway proxy. The project owner has explicitly approved Groq as the primary cloud inference provider and NVIDIA NIM as the secondary cloud inference provider for Review Master.

Review Master requires high-throughput, low-latency structured JSON generation with deterministic schema compliance, resilient failover, and strict operational cost and latency controls.

## Decision
1. **Primary Provider:** Groq Cloud API (`https://api.groq.com/openai/v1/chat/completions`) using fast, high-throughput models (e.g. `llama-3.3-70b-versatile`).
2. **Secondary / Backup Provider:** NVIDIA NIM Cloud API (`https://integrate.api.nvidia.com/v1/chat/completions`) using enterprise-grade models (e.g. `meta/llama-3.3-70b-instruct`).
3. **OpenAI-Compatible REST Interface:** Rather than introducing third-party gateways (such as LiteLLM) or heavy proprietary SDKs, Review Master implements a lightweight, native provider abstraction using `httpx`. Both Groq and NVIDIA NIM expose standard OpenAI-compatible `/chat/completions` endpoints with JSON mode / structured schema enforcement.
4. **Controlled Failover Policy:**
   - Groq is attempted first.
   - Failover to NVIDIA NIM occurs strictly upon:
     - HTTP 429 (Rate limiting / quota exhaustion)
     - HTTP 500, 502, 503, 504 (Temporary upstream server failures)
     - Network connection errors or socket timeouts
   - Failover does **not** occur for client-side errors:
     - HTTP 400 (Bad request / malformed JSON)
     - HTTP 401 / 403 (Invalid credentials)
     - Model not found / invalid prompt configuration
     - Schema validation failures
   - Bounded retries (maximum 2 attempts) with exponential backoff and absolute timeout caps.
5. **Security and Provenance Guarantees:**
   - Provider API keys (`GROQ_API_KEY`, `NVIDIA_API_KEY`) are managed exclusively through server-side environment configuration.
   - Provider keys are never logged, persisted in the database, returned in API responses, or exposed to the frontend/browser extension.
   - Every completed analysis records `provider`, `model`, latency, and token usage metadata.
   - LLMs extract community opinions; they never determine canonical product identity, fabricate specifications, or calculate deterministic product evaluation scores.

## Consequences
- Clean separation of concerns with minimal external runtime dependencies.
- Zero risk of single-provider cloud downtime halting background review processing.
- Predictable and auditable cost and latency tracking.

