# Review Master — Implementation & System Working Guide

> **Audience:** Engineering Leadership, Product Managers, Investors, and Company Stakeholders.  
> **Purpose:** Plain-language, rigorous explanation of how Review Master works, how it is implemented, how requests flow through the system, and why it is built this way.

---

## 1. Executive Overview & Value Proposition

### 1.1 The Core Problem
E-commerce review systems are fundamentally broken:
- **Review Inflation & Fake Reviews:** 5-star ratings are flooded with sponsored, incentivized, or bot-generated text.
- **Spec Obfuscation:** Vendors use inconsistent naming, confusing technical units, and obscure model numbers to mislead buyers.
- **LLM Hallucinations:** Asking general LLMs (like standard ChatGPT) for product advice leads to invented specs, outdated prices, and unverified subjective recommendations.

### 1.2 The Review Master Solution
**Review Master is an evidence-driven, deterministic product evaluation and decision-support engine.**
It operates on an uncompromising guiding principle:

> **"Every score shown to a user is computed by a published, versioned mathematical model from traceable evidence with an explicit confidence level. The AI never guesses or invents scores."**

---

## 2. End-to-End System Flow: How Review Master Works

When a user browses a product on a supported marketplace (e.g., an external SSD on Amazon) with the Review Master extension enabled, here is exactly what happens across the system:

```
[User Browser / Extension]
          │
          ▼ 1. Extract raw listing URL & title (No private cookies/data)
┌──────────────────────────────────────────────────────────────────┐
│ FASTAPI GATEWAY (/api/v1/products/identify)                      │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼ 2. Identity Matching Skill (Deterministic Match)
┌──────────────────────────────────────────────────────────────────┐
│ CATALOG MODULE                                                   │
│ • Match by MPN, GTIN, or canonical fingerprint                   │
│ • Resolve exact Variant (e.g., 1TB vs 2TB, Black vs Silver)     │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼ 3. Spec Normalization
┌──────────────────────────────────────────────────────────────────┐
│ NORMALIZATION MODULE                                             │
│ • Category schema validation (smartphones, laptops, SSDs)        │
│ • Unit conversion (e.g., MB/s vs Gbps, lbs to kg, Wh to mAh)     │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼ 4. Evidence Assembly & Trust Tiers
┌──────────────────────────────────────────────────────────────────┐
│ EVIDENCE MODULE                                                  │
│ • Pull verified benchmarks, lab tests, teardowns, specs          │
│ • Tier 1: Lab/Independent tests | Tier 2: Manufacturer specs     │
│ • Tier 3: Marketplace listings   | Tier 4: Unverified community  │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼ 5. Deterministic Evaluation Engine (NO LLM)
┌──────────────────────────────────────────────────────────────────┐
│ EVALUATION MODULE (Pure Python Function)                         │
│ • Load immutable Evaluation Model Version (e.g. SSD v1.0)        │
│ • Compute weighted parameter scores (Read/Write, Thermal, etc.)  │
│ • Missing data = NULL (Not 0)                                    │
│ • Calculate Confidence Metric (Coverage % × Trust Tier Weight)   │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼ 6. Edge AI Explanation (Grounded LLM via LiteLLM)
┌──────────────────────────────────────────────────────────────────┐
│ AI ORCHESTRATOR (LangGraph + LiteLLM)                            │
│ • LLM receives ONLY structured numbers & verified evidence       │
│ • Generates readable summary: "Why is this SSD rated 8.4?"       │
│ • Grounding Validator ensures LLM quotes ONLY actual data        │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼ 7. Response Delivered to User
┌──────────────────────────────────────────────────────────────────┐
│ PRESENTATION LAYER (Extension Sidepanel / Web App)               │
│ • Overall Score (e.g. 8.4/10)                                    │
│ • Confidence Level (e.g. 92% High Confidence)                    │
│ • Transparent Evidence Breakdown & Price History                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. The 3 Distinct Trust Outputs Explained

Traditional sites lump everything into one misleading 5-star number. Review Master cleanly separates results into **three independent trust outputs**:

| Trust Output | Who Produces It | Meaning |
|---|---|---|
| **1. Review Master Score** (0–10) | **Deterministic Engine** (Pure math, no AI) | Category-specific evaluation based on verified specs and lab benchmarks. Immutable, reproducible, auditable. |
| **2. Confidence & Evidence** | **Deterministic Engine** | Tells the user *how much reliable data exists*. If evidence is missing, the score is explicitly marked *"Limited Confidence"* rather than penalizing the product with a fake zero. |
| **3. Community & Market Signals** | **Statistical Analysis + AI Summary** | Aggregated user feedback, detected review anomalies (burst patterns, repetition), and price-to-value analysis. Kept strictly separate from the product quality score. |

---

## 4. Technical Architecture: What Tech Powers What

Review Master is built as a **Modular Monolith** for Phase 1. This gives the team the velocity of a single codebase while maintaining strict architectural boundaries that allow easy microservice extraction later.

```
                      ┌────────────────────────────┐
                      │    CLIENT APPLICATIONS     │
                      │ • Chrome Extension (MV3)   │
                      │ • Web App (React 18 + Vite)│
                      │ • Developer / B2B API      │
                      └─────────────┬──────────────┘
                                    │ HTTPS / REST / Webhooks
                                    ▼
                      ┌────────────────────────────┐
                      │     EDGE SECURITY & API    │
                      │ • FastAPI (/api/v1)        │
                      │ • JWT + API Key Auth       │
                      │ • Redis Rate Limiting      │
                      │ • Idempotency-Key Support  │
                      └─────────────┬──────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
┌──────────────┐             ┌──────────────┐             ┌──────────────┐
│  POSTGRES 17 │             │ REDIS 7 +    │             │  SEAWEEDFS   │
│ Source of    │             │ CELERY       │             │ S3 Storage   │
│ Truth (RLS,  │             │ Async Tasks, │             │ (Evidence,   │
│ Outbox,      │             │ Background   │             │ Scanned docs,│
│ Audit Log)   │             │ Ingestion    │             │ Teardowns)   │
└──────────────┘             └──────┬───────┘             └──────────────┘
                                    │
                                    ▼
                      ┌────────────────────────────┐
                      │   AI ORCHESTRATOR & EDGE   │
                      │ • LangGraph State Machine  │
                      │ • LiteLLM Gateway          │
                      │ • Ollama (Local) / Claude  │
                      │ • Strict Grounding Check   │
                      └────────────────────────────┘
```

### Key Infrastructure Components
1. **API Tier (FastAPI, Python 3.12):** High-performance async ASGI server with automated Pydantic request/response validation and OpenAPI 3.1 generation.
2. **Background Workers (Celery + Redis):** Offloads long-running tasks: price scraper updates, document virus scanning (ClamAV), review anomaly batch jobs, and webhook dispatching.
3. **Database (PostgreSQL 17):**
   - **Row-Level Security (RLS):** Complete multi-tenant data isolation.
   - **Append-Only Auditing:** Evaluations, price history, and model versions are strictly append-only.
   - **Transactional Outbox:** Guaranteed event delivery for webhooks and downstream systems without distributed 2PC locks.
4. **AI Gateway (LiteLLM):** Isolates application code from LLM vendor SDKs. Allows instantaneous switching between local Ollama models (cost-free local dev) and cloud providers (Claude, OpenAI, Gemini) while enforcing per-key spending caps.
5. **Object Storage (SeaweedFS / S3):** Stores evidence PDFs, lab bench test outputs, and images.

---

## 5. Why This Architecture Wins (Strategic Business Advantages)

### 1. Zero Hallucination Risk in Scoring
Because scoring is written as pure mathematical formulas inside versioned YAML models, Review Master can legally and technically stand behind every single score in enterprise contracts, audits, or legal reviews.

### 2. Commercial Neutrality & Fraud Resistance
Brands and advertisers cannot "buy" better scores. The API has zero write endpoints for scores. Any score recalculation requires publishing a new versioned evaluation model that impacts all products in that category uniformly.

### 3. Extremely Low Cloud & LLM Costs
90% of requests (lookups, comparisons, spec views, price checks) hit Redis cache and PostgreSQL directly, costing **$0.00 in LLM tokens**. LLMs are called only when a user requests conversational synthesis or natural language search.

### 4. B2B Commercial API Ready from Day 1
The architecture includes API-key management with monthly quota metering, scoped permissions, and HMAC-signed webhooks, making Review Master instantly sellable as a B2B Product Intelligence API to e-commerce aggregators and procurement platforms.

---

## 6. Implementation Delivery Roadmap (Phases 0 to 5)

| Phase | Milestone | Deliverables |
|---|---|---|
| **Phase 0** | **Stack Initialization & Smoke Test** | Verify Docker Compose, set up Alembic migrations, establish CI pipeline with `golden` test gate. |
| **Phase 1** | **Core Catalog, Specs & Admin** | Product variant identification, unit normalization, marketplace adapter for V1 store, admin mapping tools. |
| **Phase 2** | **Deterministic Evaluation Engine** | Category model parser, pure scoring functions, confidence metrics, evidence versioning, product API. |
| **Phase 3** | **Client Interfaces & AI Assist** | Chrome MV3 Extension, React Web SPA, natural-language requirement extractor, grounded explanation agent. |
| **Phase 4** | **Community, Pricing & Expert Case Flow** | Price history tracking, alert webhooks, review anomaly detector, expert conflict-of-interest workflow. |
| **Phase 5** | **Hardening & Commercial API** | B2B API key quotas, rate-limiting tiers, penetration tests, production staging deployment. |

---

## 7. Fast-Track 4-Week Implementation Plan (In Plain English)

This 4-week plan is designed for rapid execution to deliver an end-to-end, working MVP of Review Master that can be demonstrated to leadership, investors, and test users.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         4-WEEK IMPLEMENTATION TIMELINE                      │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│     WEEK 1       │     WEEK 2       │     WEEK 3       │      WEEK 4        │
│  The Foundation  │    The Brain     │    The Face      │ The AI & Launch    │
│  & Product Data  │ (Scoring Engine) │ (Web & Extension)│    Readiness       │
├──────────────────┼──────────────────┼──────────────────┼────────────────────┤
│ • Docker & DB    │ • Evidence Store │ • React Web App  │ • Edge AI Gateway  │
│ • User Auth      │ • Pure-Math Eval │ • Browser Ext.   │ • Grounding Checks │
│ • Normalization  │ • Confidence %   │ • Comparisons    │ • Price History    │
│ • Catalog Match  │ • Golden Tests   │ • Sidepanel UI   │ • Demo Seed Data   │
└──────────────────┴──────────────────┴──────────────────┴────────────────────┘
```

---

### Week 1: Foundation, Authentication & Product Recognition
> **Goal:** Get the core system running, connect the database, and teach the system how to recognize products from shopping pages without confusion.

* **Day 1–2: Infrastructure & Database Setup**
  - Launch the core stack via Docker (`docker compose up -d`): PostgreSQL 17, Redis, and FastAPI.
  - Run initial Alembic database migrations to create the core tables (`users`, `catalog`, `categories`, `evaluations`).
  - Verify system health via `GET /healthz`.
* **Day 3: User Authentication & Security**
  - Implement basic user sign-up, login, password hashing (Argon2id), and JWT session tokens.
  - Set up role-based permissions (Consumer vs. Admin).
* **Day 4–5: Catalog & Product Normalization**
  - Create the category schemas for our initial 3 pilot categories: **Smartphones**, **Laptops**, and **External SSDs**.
  - Build the **Unit Converter** (e.g., standardizing storage so `1000 GB` and `1 TB` mean the exact same thing; converting `MB/s` to `Gbps`).
  - Build the **Product Matching Logic**: When given an e-commerce title or link, accurately match it to the exact hardware variant (e.g., distinguishing between a 256GB and a 512GB laptop).
* **Week 1 Milestone Output:**
  - ✅ You can send a product URL or title to the API and receive a cleanly structured, normalized specification sheet in return.

---

### Week 2: The Deterministic Scoring Engine & Evidence System
> **Goal:** Build the heart of Review Master — the pure mathematical scoring engine that calculates reproducible scores and confidence levels without relying on AI guesswork.

* **Day 6–7: Evidence Store & Trust Tiers**
  - Build the Evidence repository to store verified product data (lab test results, manufacturer spec sheets, teardown data).
  - Assign immutable **Trust Tiers** to incoming evidence (Tier 1: Independent lab benchmark, Tier 2: Manufacturer official sheet, Tier 3: Marketplace page).
* **Day 8–9: Pure Mathematical Scoring Engine**
  - Implement the evaluation algorithms as pure Python functions (no LLM in the loop).
  - Calculate weighted scores for key parameters (e.g., for an SSD: Sequential Read/Write, Sustained Transfer, Thermal Throttling, Price-per-GB).
  - Implement the **Confidence Calculation**: If a product has missing test data, the engine leaves the score as `null` rather than a misleading zero, and visibly lowers the Confidence score.
* **Day 10: The Determinism Safety Gate**
  - Write automated `golden` tests (`pytest -m golden`): feed in fixed specs and prove that the score never changes by even 0.01% between runs.
  - Ensure the evaluation results are saved in PostgreSQL as immutable, append-only history.
* **Week 2 Milestone Output:**
  - ✅ You can feed a product's verified specs into the engine and get an instant, auditable Review Master Score (e.g., `8.4 / 10`) paired with a Confidence Rating (`91% High Confidence`) and full evidence links.

---

### Week 3: User Interfaces — Web Dashboard & Browser Extension
> **Goal:** Build the visual products that real customers interact with on their laptops and browsers.

* **Day 11–12: React Web Application (The Hub)**
  - Initialize the React + Vite frontend dashboard.
  - Build the **Product Detail Page** showing the 3 clear outputs:
    1. Overall Score badge (0–10).
    2. Confidence meter with evidence source checklist.
    3. Community feedback summary.
  - Build a side-by-side **Comparison View** so users can compare 2 or 3 products in the same category on normalized specs.
* **Day 13–14: Chromium Browser Extension (The Shopping Assistant)**
  - Build the Manifest V3 browser extension with a modern slide-out side panel.
  - When the shopper visits a supported e-commerce product page (e.g., Amazon), the extension automatically extracts the listing title and asks the backend: *"Do we have this product?"*
  - Display the verdict, score, and pros/cons right inside the browser window without obstructing the shopping page.
* **Day 15: Client-Server Integration & Polish**
  - Connect the extension and web app to the live backend API.
  - Enforce zero score calculation on the frontend: the UI is strictly a display layer that renders what the secure backend computes.
* **Week 3 Milestone Output:**
  - ✅ A team member can open a live Amazon product page in Chrome, open the side panel, and see Review Master automatically identify the product and display its score and comparison.

---

### Week 4: Edge AI Integration, Price Alerts & Demo Launch
> **Goal:** Connect the AI explanation layer, enable price tracking, test everything thoroughly, and prepare for company demonstration.

* **Day 16–17: Edge AI Explanation Layer (LiteLLM + LangGraph)**
  - Set up LiteLLM gateway to connect to either a local model (Ollama) or cloud model (Claude / GPT).
  - Implement the **Explanation Agent**: Takes the structured numbers computed in Week 2 and turns them into a 2-paragraph human-readable explanation: *"Why this SSD scored 8.4: Excellent sustained write speeds, but runs warmer than competitors."*
  - Implement the **Grounding Validator**: Automatically checks the LLM's text against the database to guarantee that the LLM cannot hallucinate numbers or claims not backed by evidence.
* **Day 18: Price History & Deal Alerts**
  - Add simple offer/price tracking: Celery background worker records observed daily prices.
  - Allow users to set a price alert (e.g., *"Notify me when this drops below ₹8,000"*) with email notifications via Mailpit.
* **Day 19: Data Seeding & End-to-End Testing**
  - Seed the database with 20–30 real, popular products across Smartphones, Laptops, and SSDs with complete evidence packages.
  - Conduct full smoke tests: verify extension on live web pages, test search, test comparisons, and verify responsive mobile web layouts.
* **Day 20: Executive Demo Preparation**
  - Finalize sample user walkthroughs and slide deck.
  - Rehearse the live demo showing:
    1. Extension detecting a product on Amazon.
    2. Side-by-side comparison on the Web App.
    3. AI explaining *why* one product is recommended over another based on verified lab tests.
* **Week 4 Milestone Output:**
  - ✅ A polished, fully functional Review Master MVP ready for internal company demo, investor presentation, and pilot user testing.

---



