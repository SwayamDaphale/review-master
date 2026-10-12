## What and why
<!-- Summary. Link the user story IDs (for example US-008) and any ADR. -->

Stories: US-___

## Checklist
- [ ] Acceptance criteria and test conditions from the story are covered by automated tests
- [ ] Scoring touched? Golden fixtures updated **and** a new evaluation model version created (never silently change a score)
- [ ] Database change? Alembic migration is backward-compatible for one release (expand, migrate, contract)
- [ ] New or changed endpoint? OpenAPI updated; permission/scope and tenant checks included
- [ ] Any new tenant-owned table has `org_id` and an RLS policy with a test
- [ ] Material change audited (audit log / `ai_runs`) where the story requires it
- [ ] AI text? Grounding validation and fallback covered; AI output labelled
- [ ] No secrets, tokens or personal data in code, logs or fixtures
- [ ] Docs updated (architecture, AGENTS, SKILLS, data model) or ADR added if a decision changed
- [ ] Extension manifest permissions unchanged (or justified)

## Screenshots / notes
