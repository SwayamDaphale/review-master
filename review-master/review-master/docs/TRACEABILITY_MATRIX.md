# Traceability Matrix — User Stories to Architecture

Maps every user story (US-001 to US-053) to the backend module, architecture section, API endpoints, tables, agents/skills, delivery phase and test approach that implement it. The full matrix with test approach and notes is in `../requirements/Review_Master_Traceability.xlsx` (filterable, with formula-driven coverage counts).

**Verification:** at build time every endpoint in this mapping was checked against `api/openapi.yaml`, every table against `DATA_MODEL.md`, and every skill/agent against `SKILLS.md`/`AGENTS.md`. Nothing referenced here is missing from the documents.

Phase and sprint ranges come from `DELIVERY_PLAN.md`. `Planned` means the story is V2/V3 and its endpoint is not yet in the API skeleton.

## V1 — controlled MVP

| Story | Title | Pri | Phase | Module(s) | Endpoints | Key tables | Agents / skills |
|---|---|---|---|---|---|---|---|
| US-002 | Resolve canonical product and variant | Must | Phase 1 | catalog | `POST /api/v1/products/identify` | product_families, listings, product_mappings, match_candidates, variants | match_product, resolve_variant, Identity Matching Assistant |
| US-003 | Correct product identification | Must | Phase 1 | catalog + admin | `POST /api/v1/products/corrections` | product_corrections, audit_log | - |
| US-004 | View normalized specifications | Must | Phase 1 | normalization | `GET /api/v1/variants/{variant_id}`<br>`GET /api/v1/products/{product_id}` | categories, variants | normalize_specs, convert_units |
| US-005 | Search products on the website | Must | Phase 1 | catalog | `GET /api/v1/products` | products | - |
| US-033 | Manage users, roles, and permissions | Must | Phase 1 | auth + admin | `GET /api/v1/users/me`<br>`GET /api/v1/admin/users`<br>`PUT /api/v1/admin/users/{user_id}/roles` | users, memberships, audit_log | check_permission, log_trace |
| US-034 | Manage categories and versioned evaluation models | Must | Phase 1 | evaluation + admin | `GET /api/v1/admin/evaluation-models`<br>`GET /api/v1/admin/evaluation-models/{model_id}`<br>`POST /api/v1/admin/evaluation-models/{model_id}/versions`<br>`POST /api/v1/admin/evaluation-model-versions/{version_id}/publish` | evaluation_models, evaluation_model_versions, audit_log | log_trace |
| US-035 | Manage product mappings and ambiguous matches | Must | Phase 1 | admin + catalog | `GET /api/v1/admin/mappings/queue`<br>`POST /api/v1/admin/mappings/{item_id}/resolve` | product_mappings, match_candidates, audit_log | log_trace |
| US-036 | Protect and manage evidence | Must | Phase 1 | evidence + admin | `POST /api/v1/evidence`<br>`POST /api/v1/evidence/{evidence_id}/versions` | evidence, evidence_versions, evidence_documents | check_upload_safety, attach_trust_tier |
| US-037 | Audit log of material changes | Must | Phase 1 | admin | `GET /api/v1/admin/audit-log` | audit_log, ai_runs | log_trace |
| US-006 | View product page with separated trust outputs | Must | Phase 2 | evaluation + community + expert (read) | `GET /api/v1/variants/{variant_id}` | evaluations, feedback, expert_assessments, offers | Response Assembler |
| US-008 | Deterministic category-based evaluation | Must | Phase 2 | evaluation | `GET /api/v1/variants/{variant_id}/evaluation` | evaluation_model_versions, evaluations, parameter_results | score_parameter, resolve_evidence_conflict, renormalize_weights, compute_confidence, aggregate_evaluation |
| US-009 | View Review Master score and parameter scores | Must | Phase 2 | evaluation | `GET /api/v1/variants/{variant_id}/evaluation` | evaluations, parameter_results | cache_lookup, compute_value_signal |
| US-010 | View confidence level separate from score | Must | Phase 2 | evaluation | `GET /api/v1/variants/{variant_id}/evaluation` | evaluations | compute_confidence, compute_freshness |
| US-011 | Inspect evidence and its provenance | Must | Phase 2 | evidence | `GET /api/v1/evidence/{evidence_id}`<br>`GET /api/v1/evidence/{evidence_id}/versions` | evidence, evidence_versions, evidence_documents | attach_trust_tier, classify_source_label |
| US-013 | View evaluation history | Should | Phase 2 | evaluation | `GET /api/v1/variants/{variant_id}/evaluation/history` | evaluations | - |
| US-001 | Detect product on supported marketplace page | Must | Phase 3 | Extension + catalog | `POST /api/v1/products/identify` | listings, proposed_attributes | match_product, Product Extraction Agent |
| US-018 | Compare products side by side | Must | Phase 3 | comparison | `POST /api/v1/comparisons` | comparisons | build_comparison_matrix |
| US-020 | Discover alternatives | Must | Phase 3 | comparison | `GET /api/v1/variants/{variant_id}/alternatives` | variants, evaluations | build_comparison_matrix |
| US-021 | Enter requirements in natural language | Must | Phase 3 | recommendation + ai | `POST /api/v1/recommendations/requirements` | ai_runs | Requirement Extraction Agent, validate_requirements_schema, sanitize_untrusted_text |
| US-022 | Apply hard constraints before ranking | Must | Phase 3 | recommendation | `POST /api/v1/recommendations` | recommendations | apply_hard_constraints, suggest_constraint_relaxation |
| US-023 | Personalized recommendations with explanation | Must | Phase 3 | recommendation + ai | `POST /api/v1/recommendations` | recommendations, ai_runs | rank_candidates, Recommendation Explanation Agent, validate_grounding, emit_event |
| US-007 | Save products | Should | Phase 3 | user_space | `GET /api/v1/saved-products`<br>`POST /api/v1/saved-products`<br>`DELETE /api/v1/saved-products/{saved_id}` | saved_products | emit_event |
| US-012 | AI explanation of an evaluation | Should | Phase 3 | ai | `POST /api/v1/evaluations/{evaluation_id}/explanation` | ai_runs | Evaluation Explanation Agent, validate_grounding, sanitize_untrusted_text |
| US-019 | AI comparison summary | Should | Phase 3 | ai | `POST /api/v1/comparisons` | ai_runs | Comparison Summary Agent, validate_grounding |
| US-024 | Manage my preferences | Should | Phase 3 | user_space | `GET /api/v1/preferences`<br>`PUT /api/v1/preferences` | user_preferences | - |
| US-014 | Submit structured feedback | Must | Phase 4 | community | `POST /api/v1/variants/{variant_id}/feedback` | feedback | rate_limit_check |
| US-015 | View community insights | Must | Phase 4 | community + ai | `GET /api/v1/variants/{variant_id}/community` | review_analysis, feedback | Feedback Intelligence Agent |
| US-017 | Moderate community feedback | Must | Phase 4 | admin + community | `GET /api/v1/admin/moderation/queue`<br>`POST /api/v1/admin/feedback/{feedback_id}/moderate` | moderation_actions, audit_log | log_trace, emit_event |
| US-025 | View current offers | Must | Phase 4 | pricing + adapters | `GET /api/v1/variants/{variant_id}/offers` | offers, listings | compute_freshness |
| US-016 | Review-quality signals | Should | Phase 4 | community | `GET /api/v1/variants/{variant_id}/community` | review_quality_signals | detect_near_duplicates, detect_review_bursts, build_review_quality_signals |
| US-026 | View price history | Should | Phase 4 | pricing | `GET /api/v1/variants/{variant_id}/price-history` | price_records | get_price_context, record_price_observation |
| US-027 | Create price and target-price alerts | Should | Phase 4 | pricing + notifications | `GET /api/v1/price-alerts`<br>`POST /api/v1/price-alerts`<br>`DELETE /api/v1/price-alerts/{alert_id}` | price_alerts, notifications | evaluate_price_alert, record_price_observation |
| US-028 | Control notification types | Should | Phase 4 | user_space + notifications | `GET /api/v1/notification-settings`<br>`PUT /api/v1/notification-settings` | notification_settings, notifications | - |
| US-029 | Create investigation case from potential issue | Should | Phase 4 | expert + admin | `POST /api/v1/expert-cases` | expert_cases, audit_log | log_trace |
| US-030 | Assign expert with conflict-of-interest check | Should | Phase 4 | expert + admin | `POST /api/v1/expert-cases/{case_id}/assign` | experts, expert_assignments, coi_declarations | check_permission |
| US-031 | Submit expert assessment with proof | Should | Phase 4 | expert + evidence | `POST /api/v1/expert-cases/{case_id}/assessments` | expert_assessments, evidence_documents | check_upload_safety |
| US-032 | Quality review and publish expert assessment | Should | Phase 4 | expert + evaluation | `POST /api/v1/expert-assessments/{assessment_id}/review` | expert_assessments, evidence_versions, evaluations | attach_trust_tier, aggregate_evaluation, emit_event |
| US-038 | Monitor integrations and system health | Should | Phase 4 | admin + catalog (adapters) | `GET /api/v1/admin/integrations` | integrations, jobs | emit_event |
| US-039 | Keep commercial relationships out of scoring | Must | Phase 5 | all (negative requirement) | none (negative requirement) | audit_log | check_permission |
| US-040 | Access versioned secure APIs | Must | Phase 5 | API layer + auth | `GET /api/v1/api-keys`<br>`POST /api/v1/api-keys`<br>`DELETE /api/v1/api-keys/{key_id}` | api_keys, usage_events | generate_api_key, verify_api_key, rate_limit_check, meter_usage |
| US-041 | Receive signed webhooks for events | Should | Phase 5 | events | `GET /api/v1/webhooks`<br>`POST /api/v1/webhooks`<br>`DELETE /api/v1/webhooks/{webhook_id}`<br>`GET /api/v1/webhooks/{webhook_id}/deliveries`<br>`POST /api/v1/webhooks/{webhook_id}/deliveries/{delivery_id}/replay` | webhooks, webhook_deliveries, event_outbox | emit_event, sign_webhook |

## V2 — active shopping assistant

| Story | Title | Pri | Phase | Module(s) | Endpoints | Key tables | Agents / skills |
|---|---|---|---|---|---|---|---|
| US-042 | Conversational product Q&A | Should | V2 | ai (chat) | `POST /api/v1/chat/messages` | ai_runs | Conversational Q&A Agent, Orchestrator, validate_grounding, check_permission |
| US-043 | Buy / track / wait guidance | Should | V2 | pricing | Planned - not in skeleton | price_records | buy_track_wait_guidance, get_price_context |
| US-044 | Add an authorized marketplace adapter | Should | V2 | catalog + admin (adapters) | Planned - not in skeleton | marketplaces, integrations | - |
| US-048 | Product-intelligence commercial API | Should | V2 | API layer + auth | `GET /api/v1/api-keys` | api_keys, usage_events, organizations | meter_usage, rate_limit_check |
| US-045 | Mobile app: share URL and compare | Could | V2 | mobile client | Reuses V1 endpoints | - | - |
| US-046 | Post-purchase feedback with purchase verification | Could | V2 | community | Planned - not in skeleton | feedback | check_upload_safety |
| US-047 | Brand profile and evidence submission | Could | V2 | admin + evidence (brand) | Planned - not in skeleton | evidence | attach_trust_tier |
| US-049 | Retrieve answers from approved documents (RAG) | Could | V2 | ai (RAG) | `POST /api/v1/evidence` | evidence_documents | semantic_search, apply_trust_weighting, check_upload_safety |

## V3 — long-term vision

| Story | Title | Pri | Phase | Module(s) | Endpoints | Key tables | Agents / skills |
|---|---|---|---|---|---|---|---|
| US-050 | Context-aware questions via context graph | Could | V3 | ai (context graph) | Planned - not in skeleton | - | graph_lookup |
| US-051 | Predictive price and quality-change detection | Could | V3 | pricing + evaluation | Planned - not in skeleton | price_records, evaluations | - |
| US-052 | Household / multi-user shopping | Could | V3 | user_space | Planned - not in skeleton | - | - |
| US-053 | Add a new domain evaluation model (restaurants, hotels, services) | Could | V3 | evaluation + admin | `POST /api/v1/admin/evaluation-models` | products, evaluation_models | - |

## Coverage by backend module

| Module | Stories |
|---|---|
| API layer | US-040, US-048 |
| Extension | US-001 |
| adapters | US-025 |
| admin | US-003, US-017, US-029, US-030, US-033, US-034, US-035, US-036, US-037, US-038, US-044, US-047, US-053 |
| ai | US-012, US-015, US-019, US-021, US-023, US-042, US-049, US-050 |
| all | US-039 |
| auth | US-033, US-040, US-048 |
| catalog | US-001, US-002, US-003, US-005, US-035, US-038, US-044 |
| community | US-006, US-014, US-015, US-016, US-017, US-046 |
| comparison | US-018, US-020 |
| evaluation | US-006, US-008, US-009, US-010, US-013, US-032, US-034, US-051, US-053 |
| events | US-041 |
| evidence | US-011, US-031, US-036, US-047 |
| expert | US-006, US-029, US-030, US-031, US-032 |
| mobile client | US-045 |
| normalization | US-004 |
| notifications | US-027, US-028 |
| pricing | US-025, US-026, US-027, US-043, US-051 |
| recommendation | US-021, US-022, US-023 |
| user_space | US-007, US-024, US-028, US-052 |

## Findings from the mapping (gaps and decisions)

| # | Finding | Action |
|---|---|---|
| G1 | **No user story covers sign-up, login, email verification, MFA enrollment or session management.** The endpoints exist in the API skeleton and sequence diagram §5, but the story set only has US-033 (admin manages users/roles) and US-040 (API access). | Add stories (suggested: account sign-up and verification, login with MFA for privileged roles, session/device management) so these get acceptance criteria and tests |
| G2 | Ten V1 endpoints were missing for stories US-033, US-034, US-036, US-041, US-053 (user/role admin, model list/get/create, evidence versions, webhook delete/deliveries/replay). | **Fixed in this merge:** added to `api/openapi.yaml` (54 → 64 operations) |
| G3 | Saved products, preferences and notification settings had no owning backend module. | **Fixed in this merge:** `user_space/` module added to the package layout (ARCHITECTURE_VIEWS §3.1) |
| G4 | V2/V3 stories US-043 to US-047, US-049 to US-052 have no endpoint specified yet. | Specify at the start of V2 / V3 planning; marked `Planned` |
| G5 | US-039 (commercial separation) is a negative requirement with no endpoint. | Covered by RBAC tests and the absence of any score write path (SECURITY_THREAT_MODEL §2-3) |
| G6 | Stories blocked by open decisions: US-001, US-025, US-026 (V1 marketplace, data licensing), US-029 to US-032 (expert workflow in V1 or V2), US-034 (weights need domain experts), US-008 (`value` signal, ADR-0005). | Decide per `DELIVERY_PLAN.md` §4 |

## Operations and tables not traced to a story

API operations with no story: `GET /healthz`, `GET /readyz`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/signup`, `POST /api/v1/auth/verify-email`.

Tables not referenced by any story mapping: `auth_sessions`. Authentication tables such as sessions have no story until the missing authentication stories (G1) are written.
