# Data Model (PostgreSQL)

Column-level design for the V1 schema. This is the contract for the first Alembic migrations; adjust names during implementation, keep the rules. The table list matches architecture §6; the high-level ER diagram is there.

Conventions
- Primary keys: `uuid` (UUIDv7, time-ordered). Timestamps: `timestamptz`, UTC. Money: `numeric(14,2)` + `currency char(3)`.
- Every tenant-owned table has `org_id uuid not null` and an RLS policy (§3). Global reference tables (categories, marketplaces, canonical catalog) have no `org_id`.
- **Append-only tables** (no `UPDATE`/`DELETE` granted to the app role): `evaluations`, `parameter_results`, `evidence_versions`, `price_records`, `audit_log`, `webhook_deliveries`.
- **Immutable once published:** `evaluation_model_versions`.
- Enumerations are PostgreSQL enums or `text` + `CHECK` (decide once; prefer `CHECK` for easier migrations).
- Soft delete only where a user-facing "delete" exists (feedback, saved items); regulated deletion is handled by the retention job (§5).

---

## 1. Tables

### 1.1 `auth`

| Table | Key columns | Constraints / notes |
|---|---|---|
| `users` | `id`, `email citext`, `password_hash`, `email_verified_at`, `display_name`, `status`, `mfa_secret_enc`, `created_at` | `unique(email)`; argon2id hash; `status in (active, suspended, deleted)` |
| `organizations` | `id`, `name`, `plan`, `status`, `created_at` | A personal user gets a personal org so every row has an `org_id` |
| `memberships` | `id`, `user_id`, `org_id`, `role` | `unique(user_id, org_id, role)`; `role in (consumer, public_reviewer, expert_reviewer, admin, api_consumer, brand)` |
| `auth_sessions` | `id`, `user_id`, `refresh_token_hash`, `user_agent`, `ip`, `expires_at`, `revoked_at`, `rotated_from` | Refresh tokens are rotated; reuse of a rotated token revokes the chain |
| `api_keys` | `id`, `org_id`, `name`, `prefix`, `secret_hmac`, `scopes text[]`, `expires_at`, `last_used_at`, `revoked_at`, `created_by` | `unique(prefix)`; secret never stored, only HMAC with pepper |
| `usage_events` | `id`, `org_id`, `api_key_id`, `endpoint`, `units`, `occurred_at` | Partition by month; written asynchronously |

### 1.2 `catalog`

| Table | Key columns | Constraints / notes |
|---|---|---|
| `categories` | `id`, `key`, `name`, `schema_version`, `spec_schema jsonb`, `status` | `key` unique (`smartphone`, `laptop`, `external_ssd`) |
| `product_families` | `id`, `category_id`, `name`, `manufacturer` | |
| `products` | `id`, `entity_id`, `family_id`, `category_id`, `name`, `manufacturer`, `mpn`, `gtin`, `generation`, `status` | `entity_id` reserved for future domains (restaurants, hotels); index on `(gtin)`, `(manufacturer, mpn)` |
| `variants` | `id`, `product_id`, `configuration jsonb`, `config_hash`, `sku_label` | `unique(product_id, config_hash)`; configuration holds RAM, storage, colour-independent identity attributes |
| `marketplaces` | `id`, `key`, `name`, `adapter`, `status`, `permitted_sources jsonb` | V1 has exactly one active row |
| `listings` | `id`, `marketplace_id`, `external_id`, `url`, `variant_id null`, `match_state`, `match_confidence`, `first_seen_at`, `last_seen_at` | `unique(marketplace_id, external_id)`; `match_state in (confirmed, probable, ambiguous, unmatched)`; identity never keyed on URL |
| `offers` | `id`, `listing_id`, `seller`, `current_price`, `currency`, `availability`, `observed_at`, `source`, `provenance jsonb` | Latest-state row; history lives in `price_records` |
| `product_mappings` | `id`, `listing_id`, `variant_id`, `method`, `verified_by`, `verified_at`, `version` | Versioned; every change audited |
| `match_candidates` | `id`, `listing_id`, `variant_id`, `score`, `reasons jsonb`, `source (rules\|llm)` | LLM-sourced rows can never produce `confirmed` |
| `product_corrections` | `id`, `org_id`, `user_id`, `listing_id`, `suggested_variant_id`, `status`, `created_at` | User corrections go to the admin queue; they do not change the global mapping |
| `proposed_attributes` | `id`, `listing_id`, `name`, `raw_value`, `source_span`, `source (parser\|llm)`, `confidence` | Output of extraction before validation |

### 1.3 `evaluation`

| Table | Key columns | Constraints / notes |
|---|---|---|
| `evaluation_models` | `id`, `category_id`, `name` | One per category/domain |
| `evaluation_model_versions` | `id`, `model_id`, `version`, `status (draft\|review\|published\|retired)`, `definition jsonb`, `approved_by`, `published_at` | `unique(model_id, version)`; `definition` holds parameters, weights, normalization rules, evidence requirements, confidence policy; **immutable after `published`**; publish blocked unless weights validated (see `evaluation-models/`) |
| `evaluations` | `id`, `variant_id`, `model_version_id`, `overall_score numeric(5,2) null`, `confidence_state`, `confidence_score numeric(4,3)`, `coverage numeric(4,3)`, `limitations jsonb`, `evidence_snapshot_hash`, `created_at`, `trigger` | Append-only; index `(variant_id, created_at desc)`; "latest" is a view, not an update |
| `parameter_results` | `id`, `evaluation_id`, `parameter_key`, `score numeric(5,2) null`, `status (scored\|not_scored\|conflicted)`, `weight`, `is_critical`, `evidence_ids uuid[]`, `explanation_data jsonb` | `not_scored` has `score null` (never 0) |

### 1.4 `evidence`

| Table | Key columns | Constraints / notes |
|---|---|---|
| `evidence` | `id`, `variant_id`, `parameter_key`, `source_type`, `trust_tier`, `current_version_id`, `visibility (public\|private)` | `source_type in (independent_test, expert_test, manufacturer, marketplace, community, other_authorized)`; `trust_tier` derived from `source_type` at insert |
| `evidence_versions` | `id`, `evidence_id`, `version`, `value jsonb`, `unit`, `observed_at`, `methodology`, `verification_state`, `document_id`, `created_by`, `created_at`, `withdrawn_at` | Append-only; replacing evidence adds a version |
| `evidence_documents` | `id`, `object_key`, `sha256`, `size_bytes`, `mime`, `scan_status`, `uploaded_by`, `created_at` | `scan_status in (pending, clean, rejected, quarantined)`; only `clean` is servable |

### 1.5 `community`

| Table | Key columns | Constraints / notes |
|---|---|---|
| `feedback` | `id`, `org_id`, `user_id`, `variant_id`, `ratings jsonb`, `issues jsonb`, `usage_context`, `body`, `state (pending\|approved\|rejected\|flagged)`, `created_at`, `edited_at`, `deleted_at` | Structured fields, tied to exact variant |
| `review_analysis` | `id`, `variant_id`, `summary jsonb`, `sample_size`, `feedback_watermark`, `ai_run_id`, `created_at` | Summary statements reference `feedback_ids` |
| `review_quality_signals` | `id`, `variant_id`, `signal_type`, `strength`, `feedback_ids uuid[]`, `detected_at` | Product-level indicators only; no per-person "fake" score |
| `moderation_actions` | `id`, `feedback_id`, `moderator_id`, `decision`, `reason`, `created_at` | Rejected content is retained for audit |

### 1.6 `expert`

| Table | Key columns | Constraints / notes |
|---|---|---|
| `experts` | `id`, `user_id`, `qualifications jsonb`, `status` | |
| `expert_cases` | `id`, `variant_id`, `opened_by`, `reason`, `state`, `created_at` | `state` follows the workflow in architecture §3.9; transitions enforced in code and logged |
| `expert_assignments` | `id`, `case_id`, `expert_id`, `status`, `assigned_by`, `assigned_at` | |
| `coi_declarations` | `id`, `case_id`, `expert_id`, `declared_conflicts jsonb`, `detected_conflicts jsonb`, `blocked bool` | A conflict blocks assignment |
| `expert_assessments` | `id`, `case_id`, `expert_id`, `methodology`, `test_conditions`, `findings jsonb`, `limitations`, `state`, `approved_by`, `approved_at` | `check (approved_by is distinct from expert_user_id)` (no self-approval) |

### 1.7 `pricing`

| Table | Key columns | Constraints / notes |
|---|---|---|
| `price_records` | `id`, `offer_id`, `price`, `currency`, `availability`, `observed_at`, `source`, `provenance jsonb` | Append-only; **partition by month** on `observed_at`; `unique(offer_id, observed_at, price)` for idempotency |
| `price_alerts` | `id`, `org_id`, `user_id`, `variant_id`, `kind (drop\|target)`, `target_price`, `cooldown_until`, `active` | |

### 1.8 `user_space`

| Table | Key columns | Notes |
|---|---|---|
| `user_preferences` | `id`, `org_id`, `user_id`, `category_id`, `priorities jsonb`, `usage_context` | Private to the user |
| `saved_products` | `id`, `org_id`, `user_id`, `variant_id`, `created_at`, `deleted_at` | Keyed to canonical variant, not a URL |
| `comparisons` | `id`, `org_id`, `user_id`, `variant_ids uuid[]`, `result jsonb`, `created_at` | Same-category only |
| `recommendations` | `id`, `org_id`, `user_id`, `requirements jsonb`, `result jsonb`, `ai_run_id`, `created_at` | Stores the deterministic result and the requirements used |
| `notifications` | `id`, `org_id`, `user_id`, `type`, `payload jsonb`, `channel`, `status`, `created_at`, `sent_at` | |
| `notification_settings` | `id`, `user_id`, `type`, `channel`, `enabled` | |

### 1.9 `ops`

| Table | Key columns | Notes |
|---|---|---|
| `audit_log` | `id`, `actor_type`, `actor_id`, `org_id`, `action`, `object_type`, `object_id`, `before jsonb`, `after jsonb`, `trace_id`, `occurred_at` | Append-only; optional hash chain (`prev_hash`, `row_hash`) for tamper evidence |
| `ai_runs` | `id`, `trace_id`, `agent`, `input_refs jsonb`, `evidence_refs jsonb`, `model`, `config jsonb`, `result jsonb`, `confidence`, `approval_state`, `tokens_in`, `tokens_out`, `cost_usd`, `created_at` | One row per AI operation |
| `integrations` | `id`, `marketplace_id`, `status`, `last_sync_at`, `freshness_seconds`, `last_error` | Feeds the admin health dashboard |
| `webhooks` | `id`, `org_id`, `url`, `event_types text[]`, `secret_enc`, `active` | |
| `webhook_deliveries` | `id`, `webhook_id`, `event_id`, `attempt`, `status_code`, `latency_ms`, `next_retry_at`, `state` | |
| `event_outbox` | `id`, `event_id`, `type`, `payload jsonb`, `created_at`, `dispatched_at` | Written in the same transaction as the change |
| `jobs` | `id`, `name`, `idempotency_key`, `status`, `attempts`, `last_error`, `trace_id`, `created_at`, `finished_at` | Dead-letter visibility |

---

## 2. Relationships (core)

See the ER diagram in architecture §6. Cardinalities that matter:
- `product → variant` 1:N; `variant → listing` 1:N; `listing → offer` 1:N; `offer → price_record` 1:N.
- `evaluation_model → version` 1:N; `variant → evaluation` 1:N (history); `evaluation → parameter_result` 1:N.
- `parameter_result ↔ evidence_versions` N:M through `evidence_ids` (a link table `parameter_result_evidence` is also acceptable and gives FK integrity; prefer the link table).
- `variant → expert_case` 1:N; `expert_case → expert_assessment` 1:N.

## 3. Tenancy and security in the database

```sql
-- Per request, the API sets: SET LOCAL app.current_org = '<org uuid>';
ALTER TABLE user_space.saved_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON user_space.saved_products
  USING (org_id = current_setting('app.current_org')::uuid);

-- Audit immutability: the application role may only INSERT.
REVOKE UPDATE, DELETE, TRUNCATE ON ops.audit_log FROM app_rw;
GRANT  INSERT, SELECT ON ops.audit_log TO app_rw;
```

Roles: `app_rw` (API/worker), `app_ro` (reporting), `migrator` (Alembic), `audit_reader`. Superuser is never used by the application. Run the RLS test suite in CI (a query under org A must never see org B).

## 4. Indexing and search

- Search: `pg_trgm` GIN index on normalized `products.name`/`manufacturer`; Postgres full-text on name + key specs.
- Lookups: `(listings.marketplace_id, external_id)`, `(variants.product_id, config_hash)`, `(evaluations.variant_id, created_at desc)`, `(price_records.offer_id, observed_at desc)` per partition.
- Feed a dedicated search engine only after measured need.

## 5. Retention, deletion and privacy

- User deletion: anonymize `users` and personal `feedback`, keep audit rows with an anonymous actor id, remove saved items, alerts, preferences.
- Evidence and evaluations are product data, not personal data; they are retained for auditability.
- Retention windows (`usage_events`, `notifications`, `ai_runs` raw inputs, failed uploads) are configurable and enforced by a scheduled job; set the values with legal/privacy input.

## 6. Migration rules

- Alembic only; no manual DDL in environments.
- Expand → migrate → contract: a migration must be compatible with the previous release's code for one release.
- Every migration is tested on an empty database and on the previous release schema (CI "migration gate").
- Seed data (categories, a draft evaluation model per category, roles) lives in versioned seed scripts, not migrations.
