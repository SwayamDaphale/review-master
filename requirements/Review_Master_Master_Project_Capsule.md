# Review Master --- Master Project Capsule

**Version:** 1.0\
**Date:** 2026-10-01\
**Organization:** Pleximus Inc.\
**Purpose:** Canonical project-context document for architecture
generation, technical design, implementation planning, and future
project discussions.

> **Core idea:** Review Master is an API-first, adapter-based,
> evidence-driven, AI-assisted evaluation and decision-support platform.
> It is not merely a review aggregator, browser extension, or LLM
> product scorer.

------------------------------------------------------------------------

# 1. How this document must be used

Use this document as the primary context when generating Review Master
architecture.

The architecture must satisfy two goals:

1.  Keep V1 focused, testable, and buildable.
2.  Keep the core architecture extensible enough to support additional
    marketplaces, categories, and eventually other reviewable domains
    without redesigning the entire platform.

The preferred principle is:

> **One common intelligence/trust platform + domain-specific evaluation
> models + marketplace/integration adapters + multiple interfaces.**

The formal SRS primarily defines Review Master around e-commerce/product
evaluation. The CEO has additionally expanded the long-term vision
toward restaurants, food, places, hotels, services, and other suitable
domains. That broader scope is an architectural extensibility
requirement, not a requirement to implement every domain in V1.

------------------------------------------------------------------------

# 2. Executive summary

Review Master is intended to provide an independent product intelligence
and decision-support layer across supported e-commerce platforms.

It should help a user:

-   identify the exact product and variant,
-   normalize product information,
-   understand specifications,
-   evaluate products using category-specific parameters,
-   see evidence and confidence,
-   understand customer feedback,
-   identify potential review-quality problems,
-   access expert verification where available,
-   compare products,
-   discover alternatives,
-   receive personalized recommendations,
-   compare marketplace offers,
-   understand available price history,
-   optionally receive buy/track/wait guidance,
-   and ask natural-language questions through an AI interface.

The platform should not simply copy marketplace star ratings.

The central chain is:

``` text
Identify
  ↓
Normalize
  ↓
Verify / collect evidence
  ↓
Evaluate
  ↓
Explain
  ↓
Compare
  ↓
Personalize
  ↓
Compare offers / price
  ↓
Help the user decide
```

------------------------------------------------------------------------

# 3. North-star product definition

The formal SRS describes Review Master as a universal product evaluation
and decision-support platform.

### North-star statement

> "Show Review Master what you are considering. It evaluates the
> evidence, explains the trade-offs, compares the alternatives and helps
> you decide with confidence."

### Product principles

## Universal

Support multiple platforms and categories through adapters and canonical
models.

## Evidence first

Scores should use traceable evidence and defined evaluation rules.

## AI assisted

AI helps extract, classify, summarize, compare, explain, and understand
requirements. It must not invent product facts.

## Category aware

Evaluation parameters and weights depend on the category and intended
use.

## Transparent

Users should understand score drivers, evidence, confidence, freshness,
and limitations.

## API first

Core product, evaluation, recommendation, comparison, and event
operations should be available through secure versioned APIs and
webhooks.

## Human control

Users can correct identification and preferences. Consequential actions
require appropriate approval.

------------------------------------------------------------------------

# 4. CEO vision addendum

The CEO's meeting vision expands the system beyond a conventional
e-commerce review platform.

The CEO wants the platform to eventually support:

-   products,
-   restaurants,
-   food items,
-   places,
-   hotels,
-   services,
-   and other suitable reviewable entities.

The meeting notes also identify:

-   plugin/API,
-   website,
-   possible mobile app,
-   chatbot,
-   comparison section,
-   suggestion/recommendation section,
-   admin site,
-   product feedback,
-   improvement/labeling,
-   proof/evidence,
-   expert ratings,
-   system user types,
-   scalable architecture,
-   commercially sellable product.

The architecture should therefore support a future universal entity
model.

Example:

``` text
Review Master
│
├── Product
│   ├── Smartphone
│   ├── Laptop
│   └── SSD
│
├── Place
│   ├── Restaurant
│   ├── Cafe
│   └── Hotel
│
├── Food
│   ├── Packaged Food
│   └── Beverage
│
└── Service
    ├── Repair
    ├── Salon
    └── Delivery
```

All domains can share:

-   identity,
-   evidence,
-   evaluation infrastructure,
-   feedback intelligence,
-   expert verification,
-   confidence,
-   recommendations,
-   comparison,
-   notifications,
-   AI.

Each domain gets a different evaluation model.

------------------------------------------------------------------------

# 5. Users and roles

## 5.1 Consumer

Primary user.

Needs:

-   product/entity evaluation,
-   comparison,
-   recommendations,
-   offers,
-   evidence,
-   confidence,
-   chatbot,
-   saved items,
-   alerts.

## 5.2 Power shopper / researcher

Needs:

-   detailed comparisons,
-   parameter-level analysis,
-   evidence inspection,
-   history,
-   alternatives,
-   advanced filters.

## 5.3 Community reviewer

Submits structured Review Master feedback and product/entity
experiences.

## 5.4 Expert / tester

Can:

-   accept assigned investigations,
-   inspect evidence,
-   conduct tests,
-   upload proof,
-   provide parameter-level findings,
-   declare conflicts of interest,
-   submit assessments.

Experts should not directly alter published scores.

## 5.5 Admin / quality reviewer

Manages:

-   users,
-   permissions,
-   categories,
-   evaluation models,
-   product/entity mappings,
-   moderation,
-   investigations,
-   experts,
-   evidence,
-   scoring-model publication,
-   integrations,
-   audit logs.

## 5.6 Brand / manufacturer

Future role.

Can:

-   claim official profiles,
-   submit specifications,
-   submit evidence,
-   respond to documented issues,
-   request independent testing.

A brand cannot buy a better independent score.

## 5.7 Retail/platform partner

Provides authorized:

-   catalog information,
-   offers,
-   product data,
-   affiliate integration,
-   APIs.

## 5.8 Developer/API customer

Consumes Review Master capabilities through secure APIs.

------------------------------------------------------------------------

# 6. Core interfaces

Review Master should expose one common backend through multiple
interfaces:

``` text
                    Review Master
                         │
        ┌────────────────┼────────────────┐
        │                │                │
     Extension         Website          Mobile
        │                │                │
        └────────────────┼────────────────┘
                         │
                      Chatbot
                         │
                         ↓
                   Common APIs
```

Additional interfaces:

-   Admin portal
-   Expert portal
-   Future brand/business portal
-   Developer/API clients

No interface should implement a separate product-scoring algorithm.

------------------------------------------------------------------------

# 7. Browser extension

The browser extension is a V1 component for local testing and the
controlled pilot.

Flow:

``` text
Supported e-commerce page
        ↓
Content script
        ↓
Marketplace-specific adapter
        ↓
Normalize identity
        ↓
Review Master API
        ↓
Canonical product/variant resolution
        ↓
Retrieve evaluation
        ↓
Retrieve evidence/confidence
        ↓
Retrieve offers
        ↓
Display Review Master panel
```

The extension should show:

-   product name,
-   exact variant,
-   Review Master score,
-   parameter scores,
-   confidence,
-   evidence,
-   expert assessment,
-   community insights,
-   alternatives,
-   current offers,
-   compare/save actions,
-   AI questions.

The extension should not calculate its own score.

Security principles:

-   minimum host permissions,
-   no private cookies,
-   no private browsing-history collection,
-   no marketplace credential collection,
-   no bypass of access controls,
-   only permitted/user-authorized extraction.

------------------------------------------------------------------------

# 8. Website

The web app is a complete product discovery experience.

Main capabilities:

-   search,
-   product/entity detail,
-   evaluation,
-   comparison,
-   recommendations,
-   natural-language command,
-   saved products,
-   price tracking,
-   feedback,
-   evidence,
-   alerts.

Suggested frontend:

-   React
-   Next.js
-   TypeScript

The web application communicates with versioned backend APIs.

------------------------------------------------------------------------

# 9. Mobile application

Mobile is a later interface and should reuse the same backend.

Potential capabilities:

-   product search,
-   URL sharing,
-   product comparison,
-   chatbot,
-   saved products,
-   notifications,
-   price alerts,
-   user-submitted purchase verification.

Important limitation:

A mobile app generally cannot inspect another app's private data. Review
Master should not be designed around directly reading Amazon/Flipkart's
private app activity.

Possible purchase attribution methods:

-   authorized affiliate links,
-   authorized marketplace APIs,
-   user-shared links,
-   optional receipt/invoice verification.

Keep these concepts separate:

``` text
affiliate click
attributed conversion
verified purchase
```

A click does not necessarily mean a purchase.

------------------------------------------------------------------------

# 10. Marketplace adapter architecture

Marketplace integrations must be adapter-based.

``` text
Marketplace Adapter Interface
│
├── Amazon adapter
├── Flipkart adapter
├── Meesho adapter
├── Authorized retailer feed
└── Future marketplace adapters
```

An adapter can expose capabilities such as:

-   identify listing,
-   extract permitted product attributes,
-   normalize fields,
-   identify variant,
-   retrieve offer information where permitted,
-   return source metadata,
-   return freshness,
-   return integration status.

The evaluation engine must never depend on Amazon-specific code.

V1 uses one supported marketplace for controlled testing.

Use only:

-   permitted page extraction,
-   official APIs,
-   licensed feeds,
-   authorized data providers,
-   official product information,
-   authorized partnerships.

Do not scrape private accounts, authentication cookies, or restricted
data.

------------------------------------------------------------------------

# 11. Canonical product/entity identity

Marketplace listing != canonical product.

Use a hierarchy:

``` text
Product Family
      ↓
Canonical Product
      ↓
Exact Variant
      ↓
Marketplace Listing
      ↓
Seller Offer
```

Example:

``` text
Laptop family
  ↓
Exact model/generation
  ↓
16 GB / 512 GB variant
  ↓
Amazon listing
  ↓
Seller A offer
  ↓
Price / availability / timestamp
```

Important IDs:

-   `entity_id`
-   `product_id`
-   `variant_id`
-   `marketplace_id`
-   `listing_id`
-   `offer_id`

The canonical identity must not depend on a marketplace URL.

Product matching should use:

1.  verified marketplace ID mapping,
2.  manufacturer model number,
3.  generation,
4.  exact configuration,
5.  normalized attributes,
6.  human review for ambiguous matches.

LLMs may assist extraction but should not silently merge products.

------------------------------------------------------------------------

# 12. Core architecture

Logical architecture:

``` text
                    CLIENTS
                       │
       ┌───────────────┼────────────────┐
       │               │                │
   Extension         Web             Mobile
       │               │                │
       └───────────────┼────────────────┘
                       ↓
                Chatbot / AI UI
                       ↓
               API + Security Layer
                       ↓
                CORE PLATFORM
                       │
      ┌────────────────┼─────────────────┐
      │                │                 │
 Product/Entity    Evaluation       Feedback
 Intelligence       Engine         Intelligence
      │                │                 │
 Marketplace       Evidence          Review
 Adapters          Provenance        Analysis
      │                │                 │
      └────────────────┼─────────────────┘
                       ↓
              Expert Verification
                       ↓
             Recommendation Engine
                       ↓
              Comparison Engine
                       ↓
          Offer / Price Intelligence
                       ↓
                    User
```

------------------------------------------------------------------------

# 13. Recommended backend architecture

Start as a **modular monolith**, not dozens of microservices.

Suggested modules:

``` text
FastAPI backend
│
├── Auth / RBAC
├── Product / Entity
├── Marketplace adapters
├── Evaluation
├── Evidence
├── Feedback
├── Expert workflow
├── Recommendation
├── Comparison
├── Offer / Price
├── User / Preferences
├── Notification
├── Admin
└── AI / Chat
```

Infrastructure:

``` text
PostgreSQL
Redis
Celery
Object Storage
Optional Search
Optional Vector DB
```

Later, high-load modules can be extracted into independent services.

------------------------------------------------------------------------

# 14. Data architecture

PostgreSQL should be the initial source of truth.

Core entities:

``` text
User
UserPreference
Entity/Product
ProductFamily
ProductVariant
Category
EvaluationModel
Evaluation
ParameterResult
Evidence
Marketplace
MarketplaceListing
Offer
PriceRecord
Feedback
ReviewAnalysis
Expert
ExpertCase
ExpertAssignment
ExpertAssessment
Comparison
Recommendation
SavedProduct
Notification
Activity
Integration
Webhook
AIRun
AuditLog
```

### Product

Canonical entity independent of marketplace.

### Offer

Marketplace/seller-specific commercial information.

### Evaluation

Review Master's assessment.

### Parameter

Evaluation dimension.

### Evidence

Traceable support for a parameter/evaluation.

### Feedback

Structured community experience.

### Recommendation

Links user requirements, eligible products, evaluation data, and
decision criteria.

### AI Run

Stores relevant AI operation metadata such as input/evidence references,
result, model/configuration, confidence, and approval state.

### Price Record

Timestamped price observation with provenance.

------------------------------------------------------------------------

# 15. Evaluation engine

The evaluation engine is deterministic.

It is not an LLM.

Input:

``` text
Canonical product variant
+
Validated specifications
+
Eligible evidence
+
Category evaluation model
```

Output:

``` text
Parameter results
+
Overall score
+
Confidence
+
Evidence references
+
Limitations
+
Model version
```

Flow:

``` text
Product
 ↓
Category schema
 ↓
Specifications
 ↓
Evidence
 ↓
Validation
 ↓
Normalization
 ↓
Parameter scoring
 ↓
Weighted evaluation
 ↓
Confidence
 ↓
Published evaluation
```

Missing data must not automatically become zero.

If critical evidence is missing, the system should communicate limited
or insufficient confidence.

------------------------------------------------------------------------

# 16. Category model registry

The platform needs a registry of evaluation models.

Example:

``` text
Evaluation Model Registry
│
├── Smartphone v1
├── Laptop v1
├── External SSD v1
├── Headphone v1
│
└── Future domains
    ├── Restaurant v1
    ├── Food v1
    ├── Hotel v1
    └── Service v1
```

Each model contains:

-   parameters,
-   definitions,
-   weights,
-   normalization rules,
-   evidence requirements,
-   confidence policy,
-   version,
-   status.

Historical evaluations must retain the exact model version used.

------------------------------------------------------------------------

# 17. Example evaluation parameters

These are starting design examples, not final production weights.

## Smartphone

-   performance
-   battery/charging
-   camera
-   display
-   software/updates
-   build/durability
-   connectivity/features
-   value

## Laptop

-   CPU
-   GPU
-   RAM/storage
-   display
-   battery
-   thermal/sustained performance
-   build/portability
-   connectivity/upgradeability
-   value

## External SSD

-   sequential read/write
-   sustained write
-   capacity
-   interface/compatibility
-   durability/thermal
-   warranty/endurance
-   portability/build
-   value

## Restaurant --- future example

-   food quality
-   taste
-   hygiene
-   service
-   ambience
-   value
-   waiting time
-   consistency

Final parameters and weights must be validated before publication.

------------------------------------------------------------------------

# 18. Evidence architecture

Evidence should be classified.

Possible types:

1.  Independently tested
2.  Expert-tested
3.  Manufacturer-published
4.  Marketplace-provided
5.  Community-reported
6.  Other authorized sources

Each evidence item should maintain:

-   source,
-   source type,
-   timestamp,
-   freshness,
-   verification state,
-   methodology where relevant,
-   entity/product,
-   parameter,
-   document/reference.

Never present a manufacturer claim as an independent test.

Never present a community complaint as a laboratory fact.

------------------------------------------------------------------------

# 19. Confidence

Confidence is separate from product quality.

A product can have a strong score but limited evidence.

Suggested states:

-   High confidence
-   Limited confidence
-   Insufficient evidence

Confidence may consider:

-   evidence coverage,
-   source quality,
-   verification,
-   freshness,
-   consistency,
-   critical missing parameters.

------------------------------------------------------------------------

# 20. Community feedback intelligence

Review Master should analyze feedback separately from objective
evaluation.

Potential outputs:

-   sentiment,
-   recurring issues,
-   positive experiences,
-   usage context,
-   anomaly signals,
-   review-quality indicators.

LLMs may structure and summarize feedback.

Potential anomaly signals:

-   near-identical text,
-   unusual bursts,
-   repeated patterns,
-   inconsistent product references,
-   suspicious clusters.

An anomaly is not proof of malicious behavior.

Do not automatically label a reviewer fake based on negativity, writing
style, or one unusual review.

------------------------------------------------------------------------

# 21. Expert verification workflow

This is a major CEO requirement.

Example:

``` text
Potential review/product-quality issue
        ↓
Admin triage
        ↓
Investigation case
        ↓
Expert assignment
        ↓
Conflict-of-interest check
        ↓
Evidence request
        ↓
Expert testing
        ↓
Assessment submission
        ↓
Quality review
        ↓
Approval / rejection
        ↓
Published expert assessment
        ↓
Evaluation update if evidence supports it
```

Expert assessment should include:

-   exact product/variant,
-   expert identity,
-   qualifications,
-   conflict declaration,
-   methodology,
-   test conditions,
-   evidence,
-   parameter findings,
-   limitations,
-   date,
-   approval state.

The admin should not simply replace a bad marketplace rating with an
arbitrary high rating.

The expert's findings must be evidence-backed.

Commercial relationships must be disclosed.

------------------------------------------------------------------------

# 22. Three separate trust outputs

The public product page should distinguish:

## Review Master evaluation

Evidence-based deterministic evaluation.

## Community experience

What customers report.

## Expert assessment

Independently reviewed expert findings.

External marketplace ratings can be displayed only where permitted and
should remain clearly identified as external information.

Do not blindly merge all of these into one number.

------------------------------------------------------------------------

# 23. Recommendation engine

Evaluation and recommendation are different.

### Evaluation:

"How good is this product?"

### Recommendation:

"Which eligible product fits this user?"

Pipeline:

``` text
User request
 ↓
LLM requirement extraction
 ↓
Schema validation
 ↓
Hard constraints
 ↓
Candidate products
 ↓
Evaluation/evidence/confidence
 ↓
Personalized ranking
 ↓
Offer comparison
 ↓
Recommendation
 ↓
LLM explanation
```

Example:

> "I need a 1TB external SSD under ₹8,000 for video editing and I care
> about sustained write performance."

Structured requirements:

``` json
{
  "category": "external_ssd",
  "minimum_capacity_tb": 1,
  "maximum_budget_inr": 8000,
  "use_case": "video_editing",
  "preferences": {
    "sustained_write": "high"
  }
}
```

The backend validates these fields.

Then it filters and ranks.

The LLM explains the result but does not invent the result.

------------------------------------------------------------------------

# 24. Hard constraints vs preferences

Hard constraints:

-   maximum budget,
-   minimum capacity,
-   required compatibility,
-   required features.

Preferences:

-   performance importance,
-   durability importance,
-   portability,
-   value,
-   camera,
-   battery,
-   etc.

A product failing a hard constraint must not be recommended merely
because it has a high overall evaluation.

If no product qualifies, tell the user and offer to relax a specific
constraint.

------------------------------------------------------------------------

# 25. Price intelligence

Dynamic pricing is important.

Store:

``` text
Offer
 ↓
Observed price
 ↓
Timestamp
 ↓
Price history
```

Functions:

-   current offer comparison,
-   historical price context,
-   price alerts,
-   target-price alerts,
-   buy/track/wait guidance.

Factors:

-   current price,
-   available price history,
-   data coverage,
-   user's urgency,
-   budget,
-   availability,
-   verified upcoming sale information if available.

Do not claim a future price with certainty without reliable evidence.

V1 can use simple historical context and alerts.

Advanced forecasting belongs later.

------------------------------------------------------------------------

# 26. AI / LLM responsibilities

LLM can perform:

-   natural-language product extraction,
-   category suggestion,
-   parameter extraction,
-   requirement extraction,
-   product explanation,
-   comparison summaries,
-   feedback summarization,
-   issue extraction,
-   recommendation explanations,
-   conversational product Q&A.

LLM must not silently create:

-   specifications,
-   scores,
-   evidence,
-   prices,
-   availability,
-   expert findings.

The deterministic backend remains authoritative.

------------------------------------------------------------------------

# 27. Chatbot tool architecture

Give the LLM explicit tools rather than unrestricted database access.

Possible tools:

``` text
search_products
get_product
get_evaluation
compare_products
get_offers
get_price_history
get_feedback
get_expert_assessment
save_product
create_price_alert
```

Flow:

``` text
User
 ↓
Chat API
 ↓
LLM Orchestrator
 ↓
Intent/requirements
 ↓
Tool selection
 ↓
Backend tools
 ↓
Structured results
 ↓
Evidence/permission validation
 ↓
Grounded answer
```

------------------------------------------------------------------------

# 28. RAG

RAG can retrieve:

-   expert reports,
-   product manuals,
-   approved manufacturer documents,
-   approved test reports,
-   methodology documentation.

RAG is a retrieval mechanism, not the scoring authority.

Vector retrieval must not automatically mean the retrieved statement is
verified.

------------------------------------------------------------------------

# 29. Price/purchase tracking

### Web

Browser extension can identify supported pages and product context.

### Mobile

Cannot freely inspect private Amazon/Flipkart app activity.

Use:

-   affiliate/referral attribution,
-   authorized APIs,
-   user-shared URLs,
-   optional user-submitted receipts.

Do not bypass mobile app sandboxing or private data boundaries.

------------------------------------------------------------------------

# 30. Universal domain architecture

The long-term model should generalize from `Product` to `Entity`.

``` text
Universal Entity
│
├── Product
│   ├── Smartphone
│   ├── Laptop
│   └── SSD
│
├── Place
│   ├── Restaurant
│   ├── Cafe
│   └── Hotel
│
├── Food
│   └── Packaged food
│
└── Service
    ├── Repair
    ├── Salon
    └── Delivery
```

Shared infrastructure:

``` text
Entity Identity
Evidence
Evaluation
Feedback
Expert Verification
Confidence
Comparison
Recommendation
Notifications
AI
```

Domain-specific:

``` text
Evaluation parameters
Normalization
Evidence requirements
Scoring rules
Recommendation constraints
```

This is the preferred way to make Review Master scalable beyond
e-commerce.

------------------------------------------------------------------------

# 31. Recommended technology stack

These are proposed choices, not immutable requirements.

## Frontend

-   React
-   Next.js
-   TypeScript

## Extension

-   Chrome/Chromium Manifest V3
-   TypeScript
-   content scripts
-   service worker
-   side panel

## Backend

-   Python
-   FastAPI
-   Pydantic

## Database

-   PostgreSQL

## Cache/queue

-   Redis

## Background jobs

-   Celery initially

## Evidence storage

-   S3-compatible object storage

## Search

-   PostgreSQL initially
-   dedicated search later if justified

## Vector retrieval

-   Qdrant or suitable alternative if needed

## AI

-   provider abstraction
-   LLM
-   embeddings
-   optional reranking

## Deployment

-   Docker
-   CI/CD
-   managed production database/storage

Do not introduce Kubernetes/Kafka/many microservices simply to appear
scalable. Scale according to measured requirements.

------------------------------------------------------------------------

# 32. API architecture

Version APIs from the beginning.

Suggested domains:

``` text
/api/v1/auth
/api/v1/users
/api/v1/products
/api/v1/categories
/api/v1/evaluations
/api/v1/evidence
/api/v1/feedback
/api/v1/recommendations
/api/v1/comparisons
/api/v1/offers
/api/v1/prices
/api/v1/notifications
/api/v1/chat
/api/v1/experts
/api/v1/admin
```

Potential events:

``` text
product.created
product.updated
product.evaluated
price.created
price.updated
price.changed
evaluation.created
evaluation.updated
comparison.created
comparison.completed
feedback.created
feedback.moderated
recommendation.changed
product.saved
ai.evaluation.proposed
ai.evaluation.approved
ai.evaluation.rejected
integration.connected
integration.error
integration.disconnected
```

Use:

-   authentication,
-   authorization,
-   API keys,
-   OAuth where applicable,
-   idempotency,
-   webhook signing,
-   rate limiting,
-   versioning.

------------------------------------------------------------------------

# 33. Security and governance

Required:

-   RBAC,
-   least privilege,
-   secure authentication,
-   encrypted transport,
-   secure secrets,
-   API authentication,
-   webhook signing,
-   permission scopes,
-   retention/deletion controls,
-   admin logging,
-   audit trails,
-   tenant isolation.

Private evidence must be protected.

Uploaded documents are untrusted input.

Commercial customers must not be able to directly alter independent
scores.

------------------------------------------------------------------------

# 34. Asynchronous processing

Use background jobs for:

-   marketplace ingestion,
-   product synchronization,
-   review analysis,
-   evidence processing,
-   price refresh,
-   evaluation recalculation,
-   notification delivery,
-   scheduled monitoring.

Initial:

``` text
FastAPI
 ↓
Redis
 ↓
Celery
 ↓
PostgreSQL / Object Storage
```

Future event infrastructure can be added when justified.

------------------------------------------------------------------------

# 35. Notifications

Potential:

-   in-app,
-   push,
-   email,
-   browser notifications,
-   price alerts,
-   evaluation changes,
-   low-confidence alerts,
-   stale-data reminders,
-   review-quality alerts.

Avoid notification overload.

------------------------------------------------------------------------

# 36. V1 scope

V1 is the controlled product intelligence MVP.

### Marketplace

One selected supported e-commerce website/platform.

### Categories

Approximately 3--5.

Recommended initial categories:

1.  Smartphones
2.  Laptops
3.  External storage/SSDs

### V1 workflow

``` text
Marketplace page
 ↓
Extension
 ↓
Product extraction
 ↓
Canonical product resolution
 ↓
Specification normalization
 ↓
Deterministic evaluation
 ↓
Evidence + confidence
 ↓
User requirements
 ↓
Recommendation
 ↓
Comparison
 ↓
Offer/price information
 ↓
Decision
```

### V1 must include

-   product identification,
-   normalized specifications,
-   universal product ID,
-   category models,
-   deterministic score,
-   evidence,
-   confidence,
-   community feedback,
-   comparison,
-   alternatives,
-   personalized recommendations,
-   secure APIs,
-   responsive web,
-   browser extension,
-   admin controls,
-   evaluation history,
-   feedback history,
-   price history where permitted,
-   notifications.

### V1 AI

-   extraction,
-   requirement understanding,
-   feedback summarization,
-   evaluation explanation,
-   comparison explanation,
-   recommendation explanation.

------------------------------------------------------------------------

# 37. V2 scope

V2 becomes an active shopping assistant.

Potential features:

-   more authorized marketplaces,
-   more categories,
-   voice/text requirements,
-   AI shopping brief,
-   smart ranking,
-   advanced comparison,
-   alternative discovery,
-   price/evaluation monitoring,
-   post-purchase feedback,
-   browser notifications,
-   advanced review intelligence,
-   richer expert workflow,
-   mobile app,
-   brand/manufacturer pilot,
-   commercial API.

------------------------------------------------------------------------

# 38. V3 scope

V3 becomes a universal product intelligence layer.

Formal SRS direction:

-   expanded authorized integrations,
-   context graph,
-   predictive price changes,
-   product-quality change detection,
-   evaluation-confidence change detection,
-   AI optimization,
-   risk/value/opportunity briefing,
-   controlled monitoring,
-   advanced product intelligence,
-   household/multi-user shopping,
-   advanced API framework,
-   preference learning with controls,
-   cross-platform discovery,
-   natural-language analytics.

------------------------------------------------------------------------

# 39. Context graph

Future context graph:

``` text
User Preferences
       ↓
Products / Entities
       ↓
Categories
       ↓
Specifications
       ↓
Offers
       ↓
Evaluations
       ↓
Evidence
       ↓
Community Feedback
       ↓
Comparisons
       ↓
Recommendations
       ↓
Decisions
```

This allows future AI systems to answer context-aware questions without
requiring users to manually assemble information.

------------------------------------------------------------------------

# 40. Admin and expert governance

Admin manages:

-   users,
-   categories,
-   evaluation models,
-   model versions,
-   mappings,
-   moderation,
-   expert assignments,
-   investigations,
-   evidence,
-   integrations,
-   API keys,
-   policies,
-   system health,
-   audit logs.

Expert manages assigned cases.

Neither should silently overwrite historical evidence.

All material changes should be versioned/audited.

------------------------------------------------------------------------

# 41. Commercial strategy

Potential revenue streams:

## Affiliate / commerce

Authorized affiliate/referral links.

## Expert testing

Paid independent assessment/testing.

## Brand/manufacturer tools

Subscriptions for:

-   profile management,
-   evidence submission,
-   issue analytics,
-   feedback insights.

## Product intelligence API

B2B API access to:

-   identity,
-   evaluation,
-   evidence metadata,
-   comparisons,
-   recommendations.

## Enterprise analytics

Future product/category insights using appropriate privacy controls.

Commercial relationships must not directly affect independent scoring.

------------------------------------------------------------------------

# 42. Scalability strategy

Start with modular monolith.

Scale:

-   API horizontally,
-   workers independently,
-   database with indexing/replication as needed,
-   object storage for evidence,
-   cache for frequent product results,
-   adapters independently,
-   review analysis through workers,
-   recommendation retrieval through efficient filtering.

Extract services only when there is a real need such as:

-   independent scaling,
-   different availability requirements,
-   different deployment cycle,
-   resource isolation,
-   separate team ownership.

Likely future extraction candidates:

-   marketplace ingestion,
-   review intelligence,
-   recommendation service,
-   notification service,
-   AI service.

------------------------------------------------------------------------

# 43. Data and commercial independence

The following must remain separated:

``` text
Product quality
≠
Marketplace price
≠
Affiliate revenue
≠
Community sentiment
≠
Expert assessment
≠
Personal recommendation
```

A recommendation may consider all relevant information, but each signal
must retain its meaning.

Example:

-   A product can be cheap but poor.
-   A product can be expensive but well evaluated.
-   A product can have suspicious review patterns.
-   A product can have strong expert evidence but insufficient long-term
    durability data.
-   A product can be excellent overall but fail the user's budget.

The system should explain these trade-offs.

------------------------------------------------------------------------

# 44. Testing strategy

V1 test dataset should be manually reviewed.

Test:

## Identity

-   exact product,
-   variant,
-   generation,
-   capacity,
-   ambiguous listing,
-   missing model.

## Evaluation

-   deterministic output,
-   unit normalization,
-   missing data,
-   conflicting evidence,
-   scoring version.

## Recommendation

-   hard constraints,
-   budget,
-   user preferences,
-   no eligible product,
-   low-confidence product.

## Extension

-   supported page,
-   unsupported page,
-   missing data,
-   API failure,
-   ambiguous identity.

## Security

-   unauthorized access,
-   role escalation,
-   private evidence,
-   expert self-approval,
-   malicious uploads.

------------------------------------------------------------------------

# 45. Non-functional requirements

From the formal SRS:

## Performance

Target approximately ≤2 seconds for common/cached product evaluation
retrieval under expected load.

## Usability

Common actions should be simple; SRS target is approximately ≤3 clicks
for common actions.

## Availability

Production should support availability appropriate to commercial SLA.

## Scalability

Application, database, queue, and evaluation layers must scale.

## Browser support

Extension should work reliably on supported Chromium-based browsers and
remain extensible.

## Observability

Logs, error tracking, performance monitoring, evaluation-quality
monitoring, audit logs, integration health.

## Backup

Automated backups and tested restoration.

## AI reliability

Confidence-aware extraction, traceable evidence, deterministic core
scoring, human correction.

------------------------------------------------------------------------

# 46. V1 out of scope

Do not dilute V1 with:

-   full e-commerce marketplace,
-   payment/checkout processing,
-   full inventory management,
-   complex seller management,
-   replacement of e-commerce websites,
-   replacement of manufacturer documentation,
-   advanced BI,
-   unrestricted autonomous purchasing,
-   unsupported private-account scraping,
-   authentication-cookie collection,
-   restricted data collection,
-   large document-management suite.

------------------------------------------------------------------------

# 47. Product KPIs

Track:

-   product identification accuracy,
-   evaluation response time,
-   recommendation acceptance,
-   evaluation confidence/calibration,
-   user correction rate,
-   community feedback quality,
-   decision time,
-   price-alert usefulness,
-   weekly active users,
-   API usage/retention.

Do not invent accuracy or scale numbers before establishing a test
baseline.

------------------------------------------------------------------------

# 48. Recommended development sequence

1.  Prototype Product Panel, Evaluation View, Comparison View,
    Recommendation Drawer, and Universal Command.
2.  Define canonical product/entity, evidence, evaluation, and
    permission models.
3.  Build V1 product engine, category models, deterministic scoring,
    feedback, and APIs.
4.  Integrate browser extension and responsive web.
5.  Add AI extraction, evaluation explanations, comparison suggestions,
    recommendation summaries.
6.  Pilot with a small group and measure accuracy, decision time,
    confidence, and recommendation acceptance.
7.  Build V2 assistant, voice/text requirements, advanced comparison,
    monitoring.
8.  Add additional authorized marketplace adapters.
9.  Build V3 context graph and predictive intelligence.
10. Expand to restaurants, food, places, hotels, services, and other
    domains after the core architecture is validated.

------------------------------------------------------------------------

# 49. One-page architecture summary

``` text
                         REVIEW MASTER
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
        Extension           Web              Mobile
            │                 │                 │
            └─────────────────┼─────────────────┘
                              ↓
                      API + Security
                              ↓
                  ┌───────────┴───────────┐
                  │                       │
          Product/Entity             User/Profile
          Intelligence               Preferences
                  │                       │
          Marketplace adapters            │
                  │                       │
                  ↓                       ↓
             Product DB             Recommendation
                  │                    Engine
                  ↓                       │
           Evaluation Engine              │
                  │                       │
        ┌─────────┼─────────┐             │
        │         │         │             │
     Evidence  Feedback   Experts         │
        │         │      Verification      │
        └─────────┼─────────┴─────────────┘
                  ↓
            Score + Confidence
                  ↓
         Comparison + Alternatives
                  ↓
        Offer / Price Intelligence
                  ↓
              AI Explanation
                  ↓
              USER DECISION
```

------------------------------------------------------------------------

# 50. Universal long-term architecture

``` text
                           REVIEW MASTER
                                │
                 ┌──────────────┼──────────────┐
                 │              │              │
              Consumer       Expert/Admin    Business
              Interfaces      Interfaces     Interfaces
                 │              │              │
                 └──────────────┼──────────────┘
                                ↓
                        API / Identity / RBAC
                                ↓
                       UNIVERSAL ENTITY LAYER
                                ↓
              ┌─────────────────┼─────────────────┐
              │                 │                 │
           Products            Places           Services
              │                 │                 │
       Smartphone/Laptop    Restaurant/Hotel    Repair/etc.
              │                 │                 │
              └─────────────────┼─────────────────┘
                                ↓
                     DOMAIN EVALUATION MODELS
                                ↓
                ┌───────────────┼───────────────┐
                │               │               │
             Evidence       Feedback         Experts
                │               │               │
                └───────────────┼───────────────┘
                                ↓
                         TRUST / CONFIDENCE
                                ↓
                       RECOMMENDATION ENGINE
                                ↓
                       COMPARISON ENGINE
                                ↓
                     PRICE / VALUE INTELLIGENCE
                                ↓
                        AI / CONVERSATION
                                ↓
                           DECISION
```

------------------------------------------------------------------------

# 51. Architecture rules

When generating detailed architecture, follow these rules:

1.  LLM is not the scoring authority.
2.  Product quality is separate from price.
3.  Product evaluation is separate from personalized recommendation.
4.  Canonical product is separate from marketplace listing and offer.
5.  Community feedback is separate from expert assessment.
6.  Manufacturer claims are separate from independent tests.
7.  Evaluation models are versioned.
8.  Marketplace integrations are adapters.
9.  Domain evaluation models are configurable.
10. Evidence provenance is first-class.
11. Confidence is first-class.
12. Heavy work is asynchronous.
13. PostgreSQL is the initial source of truth.
14. Vector DB is optional and retrieval-focused.
15. Mobile cannot be assumed to inspect private third-party apps.
16. Review anomalies are signals, not automatic proof of fraud.
17. Commercial relationships cannot directly modify independent scores.
18. Historical evaluations must remain auditable.
19. V1 is focused.
20. Long-term architecture is extensible.

------------------------------------------------------------------------

# 52. What an architecture generator should produce from this capsule

A detailed architecture generated from this document should include:

1.  System architecture
2.  Context diagram
3.  Container diagram
4.  Component diagram
5.  V1 modular-monolith architecture
6.  Future service-extraction architecture
7.  Product/entity data model
8.  ER diagram
9.  Marketplace adapter architecture
10. Evaluation-engine architecture
11. Evidence/provenance architecture
12. Review-intelligence architecture
13. Expert verification workflow
14. Recommendation architecture
15. AI/LLM orchestration
16. RAG architecture
17. Browser extension architecture
18. Web architecture
19. Mobile architecture
20. API architecture
21. Event/webhook architecture
22. Authentication/RBAC architecture
23. Security architecture
24. Deployment architecture
25. Observability architecture
26. Database schema
27. API contracts
28. Technology rationale
29. Scalability plan
30. Failure/retry strategy
31. Testing architecture
32. CI/CD
33. LLM cost-control strategy
34. Modular-monolith → services migration path
35. Architecture Decision Records

------------------------------------------------------------------------

# 53. Canonical project statement

> **Review Master is a scalable, API-first, adapter-based,
> evidence-driven, AI-assisted universal evaluation and decision-support
> platform.**

V1:

> **One supported e-commerce platform + approximately 3--5 product
> categories + browser extension + responsive web + deterministic
> evaluation + evidence/confidence + community feedback + comparison +
> personalized recommendation.**

Long term:

> **Multiple marketplaces + many product categories + restaurants +
> food + places + hotels + services + expert verification + mobile +
> chatbot + business portals + product-intelligence APIs.**

The central architectural idea is:

``` text
IDENTIFY
   ↓
STRUCTURE
   ↓
VERIFY
   ↓
EVALUATE
   ↓
EXPLAIN
   ↓
COMPARE
   ↓
PERSONALIZE
   ↓
PRICE / VALUE
   ↓
DECIDE
```

Review Master is therefore not fundamentally a "review website".

It is a **decision-intelligence platform built around trusted entity
identity, evidence, evaluation, feedback, expert verification,
recommendations, and explainable AI.**

------------------------------------------------------------------------

# 54. Formal source alignment

The formal source is:

**Review_Master_Product_Requirement_SRS.docx**

The SRS establishes:

-   universal product intelligence,
-   canonical product model,
-   offers,
-   evaluations,
-   parameters,
-   evidence,
-   feedback,
-   recommendations,
-   browser extension,
-   APIs,
-   webhooks,
-   security,
-   notifications,
-   AI operating model,
-   data model,
-   adapter-based integrations,
-   reporting/admin,
-   KPIs,
-   V1/V2/V3 roadmap.

The CEO vision in this capsule is explicitly treated as an additional
product-direction layer for future extensibility, particularly:

-   expert verification,
-   admin investigation,
-   mobile,
-   restaurants,
-   food,
-   places,
-   hotels,
-   services,
-   broader commercial/sellable platform.

Where CEO vision and formal V1 scope differ, **V1 remains the controlled
implementation scope while the architecture remains extensible.**

------------------------------------------------------------------------

# 55. Final instruction to Claude

When this file is supplied, first understand the complete product and
separate:

-   **V1 implementation requirements**
-   **V2 requirements**
-   **V3 requirements**
-   **CEO long-term vision**
-   **architectural extensibility requirements**
-   **future ideas that should not enter V1**

Do not collapse everything into one release.

Generate a professional, scalable architecture that is:

-   understandable,
-   implementable,
-   secure,
-   auditable,
-   commercially extensible,
-   AI-assisted but not AI-dependent,
-   modular,
-   API-first,
-   adapter-based,
-   evidence-driven,
-   and capable of future domain expansion.

The architecture must explicitly explain **why each component exists,
what owns each responsibility, what data flows between components, how
the V1 system works locally, and how it can evolve toward the long-term
universal Review Master platform.**

# END OF REVIEW MASTER MASTER PROJECT CAPSULE
