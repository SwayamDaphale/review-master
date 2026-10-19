# Sequence Diagrams — Key Flows

Mermaid sequence diagrams for the six flows a reviewer is most likely to ask about. Story IDs refer to `requirements/Review_Master_User_Stories.xlsx`.

---

## 1. Product page lookup from the extension (US-001, US-002, US-006, US-008, US-009)

```mermaid
sequenceDiagram
  autonumber
  actor U as Consumer
  participant CS as Content script
  participant SW as Service worker
  participant API as API
  participant CAT as Catalog / matcher
  participant EV as Evaluation (cached)
  participant R as Redis
  participant DB as PostgreSQL

  U->>CS: Opens a supported product page
  CS->>SW: Permitted attributes + listing id
  SW->>API: POST /api/v1/products/identify
  API->>CAT: match_product(attributes)
  CAT->>DB: Lookup mappings / variants
  DB-->>CAT: Candidates
  alt confirmed or probable
    CAT-->>API: variant_id + match_state
    API->>R: GET eval:{variant}:{model}:{hash}
    alt cache hit
      R-->>API: Evaluation payload
    else cache miss
      API->>EV: get_latest_evaluation(variant_id)
      EV->>DB: Read evaluation + parameter results + evidence refs
      DB-->>EV: Rows
      EV-->>API: Evaluation payload
      API->>R: SET (invalidate on evaluation.updated)
    end
    API-->>SW: Product, variant, evaluation, confidence, community, expert, offers
    SW-->>U: Side panel renders (probable shows "unconfirmed match")
  else ambiguous
    CAT-->>API: candidates[]
    API-->>SW: ambiguous_identity + candidates
    SW-->>U: Asks user to choose a variant
    U->>SW: Picks variant (or flags wrong match)
    SW->>API: POST /api/v1/products/corrections
    API->>DB: Store correction -> admin mapping queue (no global change)
  else unmatched
    API-->>SW: unmatched (offer: request evaluation)
  end
```

## 2. Evidence added → evaluation recalculated (US-008, US-010, US-011, US-013, US-036)

```mermaid
sequenceDiagram
  autonumber
  actor A as Admin / Expert
  participant API as API
  participant SCAN as Upload safety (scan)
  participant OBJ as Object storage
  participant DB as PostgreSQL
  participant OB as Event outbox
  participant W as Celery worker
  participant ENG as Evaluation engine (pure)
  participant R as Redis

  A->>API: Upload evidence file + metadata
  API->>SCAN: check_upload_safety(file)
  SCAN-->>API: safe / rejected / quarantined
  API->>OBJ: Store under random key (if safe)
  API->>DB: Insert evidence_version (tier set at ingestion) + audit row
  API->>OB: Insert evidence.version.created (same transaction)
  API-->>A: 202 Accepted
  OB->>W: Dispatch evaluation.recalculate(variant)
  W->>DB: Load validated specs + eligible evidence + published model version
  W->>ENG: aggregate_evaluation(inputs)
  ENG-->>W: parameters, overall|null, confidence, limitations
  W->>DB: INSERT new evaluation row (old rows untouched)
  W->>OB: Insert evaluation.updated
  OB->>R: Invalidate cached evaluation + explanation
  OB->>W: Notifications + customer webhooks
```

## 3. Natural-language recommendation (US-021, US-022, US-023)

```mermaid
sequenceDiagram
  autonumber
  actor U as Consumer
  participant API as API
  participant ORC as Orchestrator (capped)
  participant RQ as Requirement Extraction Agent
  participant SK as Skills (validate, constraints, rank)
  participant DB as PostgreSQL
  participant RX as Recommendation Explanation Agent
  participant GR as Grounding gate

  U->>API: "1 TB external SSD under ₹8,000 for video editing"
  API->>ORC: requirements flow (actor, trace_id)
  ORC->>RQ: sanitized text + category schemas
  RQ-->>ORC: Requirements JSON
  ORC->>SK: validate_requirements_schema
  alt invalid or ambiguous fields
    SK-->>ORC: clarifications_needed
    ORC-->>U: Asks a specific question
  else valid
    ORC->>SK: apply_hard_constraints(candidates)
    SK->>DB: Query eligible variants + evaluations + offers
    DB-->>SK: Data
    alt none eligible
      SK-->>ORC: empty + suggest_constraint_relaxation
    else candidates
      SK->>SK: rank_candidates (fit x confidence factor)
      SK-->>ORC: Ranked result
    end
    ORC->>RX: Ranked result (read-only)
    RX-->>ORC: Draft explanation
    ORC->>GR: validate_grounding(draft, payloads)
    alt grounded
      GR-->>U: Ranked list + explanation + confidence + trade-offs
    else not grounded
      GR-->>ORC: retry once, then deterministic template
    end
  end
```

## 4. Expert investigation → published assessment → re-evaluation (US-029 to US-032)

```mermaid
sequenceDiagram
  autonumber
  actor AD as Admin
  actor EX as Expert
  actor QA as Quality reviewer (Admin)
  participant API as API
  participant DB as PostgreSQL
  participant W as Worker
  participant ENG as Evaluation engine

  AD->>API: Open case from flagged issue / anomaly / report
  API->>DB: expert_case (case_open) + audit
  AD->>API: Assign expert
  API->>DB: coi_check (declared + detected conflicts)
  alt conflict
    API-->>AD: Blocked (conflict of interest)
  else clear
    API->>DB: expert_assigned
    EX->>API: Accept, request evidence, run tests, upload proof
    EX->>API: Submit assessment (methodology, findings, limitations)
    API->>DB: assessment_submitted -> quality_review
    QA->>API: Approve / reject / return with comments
    Note over API,DB: Expert cannot approve own assessment. Admin cannot set a score.
    alt approved
      API->>DB: Publish assessment + create tier-1 evidence record
      API->>W: evaluation.recalculate(variant)
      W->>ENG: aggregate_evaluation(...)
      ENG-->>W: New evaluation (versioned engine)
      W->>DB: Insert new evaluation row
    else rejected / returned
      API->>DB: State change + audit (never publicly visible)
    end
  end
```

## 5. Sign-up, login and API-key access (US-033, US-040)

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  actor D as Developer
  participant WEB as Web app
  participant API as API
  participant DB as PostgreSQL (auth schema)
  participant R as Redis
  participant MAIL as Email (Mailpit in dev)

  U->>WEB: Sign up (email, password)
  WEB->>API: POST /api/v1/auth/signup
  API->>DB: Create user (argon2id hash), unverified
  API->>R: Store email-verification token (TTL)
  API->>MAIL: Send verification link
  U->>API: Verify email
  U->>WEB: Login
  WEB->>API: POST /api/v1/auth/login
  API->>DB: Verify credentials, create auth_session (hashed refresh token)
  API-->>WEB: Access JWT (15 min) + refresh cookie
  Note over API: Admin and Expert roles require TOTP (MFA)

  D->>API: Request with header Authorization: Bearer rm_live_<prefix>_<secret>
  API->>DB: Lookup key by prefix
  API->>API: Constant-time HMAC compare, check scope, expiry, revocation
  API->>R: Token-bucket rate limit
  API-->>D: Response (usage metered asynchronously)
```

## 6. Price alert (US-025, US-027, US-028)

```mermaid
sequenceDiagram
  autonumber
  actor U as Consumer
  participant API as API
  participant DB as PostgreSQL
  participant W as Worker
  participant AD as Marketplace adapter
  participant N as Notification service

  U->>API: Create alert (variant, target price) (confirmed by user)
  API->>DB: price_alert
  loop schedule (per offer priority)
    W->>AD: get_offers(listing) (permitted sources only)
    AD-->>W: OfferObservation[]
    W->>DB: record_price_observation (append-only, idempotent)
    W->>W: evaluate_price_alert (cooldown 24 h, no oscillation spam)
    alt alert fires
      W->>N: Notification(price, source, timestamp)
      N-->>U: In-app + email (+ browser push)
    end
  end
```
