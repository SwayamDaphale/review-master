# Security Architecture, Threat Model and Privacy/Legal Checklist

Builds on architecture §3.16 and §8 and capsule §33. **This is a design-stage threat model, not a penetration test, and nothing in §5 is legal advice.**

---

## 1. Security principles

1. Deny by default; one central `check_permission(actor, action, resource)` used by every endpoint and every chat tool.
2. Least privilege per role, per API-key scope, per database role.
3. Tenant isolation twice: application checks **and** PostgreSQL Row-Level Security.
4. No path lets a person or customer write a score. Scores come only from the evaluation engine.
5. Everything uploaded or scraped is untrusted data. Text from marketplaces, reviews and documents is never an instruction to an LLM.
6. Every material change is audited; audit storage is append-only.
7. Secrets only in a secret manager; none in the repository, images or logs.

## 2. RBAC matrix (V1; ✓ allowed, ◐ own/assigned/scoped only, ✗ never)

| Action | Guest | Consumer | Public Reviewer | Expert | Admin | API consumer (key) | Brand (V2) |
|---|---|---|---|---|---|---|---|
| Read public evaluation, community, expert output | ✓ limited | ✓ | ✓ | ✓ | ✓ | ✓ per scope | ✓ own products |
| Save products, preferences, alerts | ✗ | ◐ own | ◐ own | ◐ own | ◐ own | ✗ | ✗ |
| Submit feedback | ✗ | ✗ | ◐ own | ✗ | ✗ | ✗ | ✗ |
| Moderate feedback | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Open expert case | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Assign expert (COI check) | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Submit expert assessment | ✗ | ✗ | ✗ | ◐ assigned case | ✗ | ✗ | ✗ |
| Approve/reject assessment | ✗ | ✗ | ✗ | ✗ (never own) | ✓ (not author) | ✗ | ✗ |
| Upload evidence | ✗ | ✗ | ✗ | ◐ assigned case | ✓ | ✗ | ◐ own, labelled manufacturer-published |
| Resolve product mappings | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Create/publish evaluation model version | ✗ | ✗ | ✗ | ✗ | ✓ (with recorded approval) | ✗ | ✗ |
| Manage users and roles | ✗ | ✗ | ✗ | ✗ | ✓ (no self-escalation) | ✗ | ✗ |
| View audit log | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Manage API keys and webhooks | ✗ | ✗ | ✗ | ✗ | ✓ | ◐ own org | ✗ |
| **Edit or set a score / verdict** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

MFA (TOTP) is required for Admin and Expert. API keys never inherit user roles; they carry explicit scopes.

## 3. Threat model (STRIDE-style, by component)

| # | Component | Threat | Mitigation | Verified by |
|---|---|---|---|---|
| 1 | Auth | Credential stuffing, weak passwords | argon2id, rate limiting and lockout/backoff, breached-password check, email verification, MFA for privileged roles | Auth abuse tests |
| 2 | Auth | Refresh-token theft/replay | Rotation with reuse detection (revoke chain), httpOnly cookie for web, short access-token lifetime | Session tests |
| 3 | API | Broken object-level authorization (read another user's saved list, preferences, feedback edits) | `check_permission` + RLS on tenant tables; ownership checks on every object access | Cross-tenant and IDOR tests |
| 4 | API | Role escalation via modified token/request | Roles read server-side from the database, signed tokens, no client-supplied roles, audit of role changes | Escalation tests |
| 5 | API keys | Key leak, brute force | Only prefix + HMAC stored, constant-time compare, scopes, expiry, revocation, per-key rate limits, secret scanning in CI | Key lifecycle tests |
| 6 | API | Abuse and scraping of the evaluation data | Rate limits, plan limits, usage metering, anomaly alerts | Load/abuse tests |
| 7 | Evaluation | Tampering with scores or evidence | No write path for scores; append-only evaluations/evidence versions; published model versions immutable; audit log; commercial keys cannot write | Determinism gate, permission tests |
| 8 | Evidence uploads | Malware, oversized or disguised files, path tricks | Type/size validation, malware scan, random object keys, no server-side execution, quarantine state, signed short-lived download URLs | Malicious upload tests |
| 9 | Private evidence | Unauthorized download | Visibility flag + permission check before issuing a signed URL | Private-evidence tests |
| 10 | Expert workflow | Self-approval, conflict of interest | DB check constraint and code rule (author ≠ approver), COI declaration + detection blocks assignment | Workflow tests |
| 11 | LLM / chat | Prompt injection via marketplace text, reviews or documents | Untrusted-text sanitization, tool-only data access, per-tool permission checks, write tools need user confirmation, grounding validation | Injection tests |
| 12 | LLM / chat | Data leakage across tenants through prompts or cache | Tenant ID in cache keys, RAG filters on `org_id`, no cross-tenant context in prompts | Tenant tests |
| 13 | LLM cost | Cost-abuse (deliberately expensive requests) | Caps on tool calls/iterations, per-request and per-tenant budgets, rate limits, caching | Budget tests |
| 14 | Marketplace adapters | Scraped content poisoning (malicious HTML/scripts, fake specs) | Parse as data, strip scripts, validate against category schema, attributes tagged by source, human review for ambiguity | Adapter fixtures |
| 15 | Extension | Over-broad permissions, token exposure to the page | Minimum host permissions, no cookies/history, token only in the service worker, permission gate in CI | Manifest check |
| 16 | Webhooks | Forged or replayed deliveries; SSRF through customer URLs | HMAC signature + timestamp, event IDs, block private/internal IP ranges when delivering, timeouts | Webhook tests |
| 17 | Database | SQL injection, over-privileged app role | ORM/parameterized queries, least-privilege roles, audit role is INSERT-only, no superuser use | SAST + DB role tests |
| 18 | Review system | Review manipulation | Signals (not verdicts), moderation, verified-purchase states where available | Anomaly fixtures |
| 19 | Supply chain | Malicious dependencies/images/actions | Dependency audit, image scan, pinned versions and action SHAs, lockfiles, Dependabot | CI scans |
| 20 | Operations | Secret exposure in logs/env | Log redaction, secret manager, `.env` ignored by git, secret scan | gitleaks |
| 21 | Availability | Resource exhaustion, queue flooding | Rate limits, queue-per-job-type, timeouts, backpressure | Load tests |

## 4. Security controls checklist (before pilot)

- [ ] TLS everywhere; HSTS on web; secure cookie flags
- [ ] CORS restricted to known origins; CSRF protection for cookie-based flows
- [ ] RLS policies on every tenant table with automated tests
- [ ] Audit and AI-run logging verified for every material action
- [ ] Backup restore drill completed
- [ ] Secrets in a manager; rotation procedure documented
- [ ] Dependency, image and secret scans green in CI
- [ ] Extension permission gate green; store listing justifies each permission
- [ ] Rate limits and budgets configured
- [ ] Incident response contact list and runbook exist
- [ ] External security review or penetration test scheduled (recommended before commercial launch)

## 5. Privacy and legal checklist (questions to answer with counsel — not advice)

| Topic | Question to resolve |
|---|---|
| Marketplace terms of service | Do the V1 marketplace's terms and official APIs permit the planned extraction, storage and display of listing, price and review data? Which sources are officially licensed? |
| Review and content ownership | What may be stored and shown from marketplace reviews? Review Master's own community feedback needs terms of use and a content licence |
| Personal data | What personal data is processed (account, saved items, alerts, feedback, analytics, IP addresses)? Lawful basis, purposes, retention, deletion and export. Which regime applies to the target market (for example India's DPDP Act, GDPR if EU users)? |
| Consent and analytics | Is consent needed for analytics and notifications (email/push)? |
| Extension store policy | Browser store rules on permissions, single purpose and user-data handling |
| Affiliate and advertising disclosure | What disclosure labels are required where affiliate links or commercial relationships exist? (The architecture already requires disclosure labels.) |
| Expert and brand relationships | Contracts for experts (independence, conflict declaration) and brands (paid testing never buys a better score) |
| AI transparency | Labelling of AI-generated text and any regional rules on automated decisions |
| Data residency | Where may data be stored and processed (cloud region, LLM provider region)? |
| Liability wording | Terms and in-product wording about evaluations being evidence-based decision support, not guarantees |
| Third-party licences | Open-source licences of dependencies and images (for example check the licence of the graph database and gateway if distributed commercially) |

## 6. Incident handling (outline)

Detect (alerts, user reports) → triage severity → contain (revoke keys/sessions, disable adapter or feature flag) → investigate with `trace_id` and audit log → restore → notify as required → post-incident review with action items.
