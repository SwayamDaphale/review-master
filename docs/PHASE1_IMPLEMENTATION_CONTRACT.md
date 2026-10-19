# Review Master â€” Phase 1 Implementation Contract

**Scope:** user-initiated extraction of smartphone listing information from Amazon India into downloadable JSON.
**Status:** initial contract draft for implementation review.
**Non-goal:** no database, scoring, recommendations, background crawling, AI, or browser-history collection in this phase.

## Decisions fixed for Phase 1

- Target category: smartphones only.
- Target marketplace: Amazon India (`amazon.in`).
- Extraction starts only when the user opens a supported product page and explicitly clicks the extension action.
- The extension extracts available page-visible fields; it does not bypass access controls or anti-bot measures.
- Output is a downloadable JSON snapshot validated against `smartphone-extraction-1.0.schema.json`.
- Missing or uncertain values are `null` and/or explicit validation warnings; never invent a value or substitute zero for missing data.
- Preserve raw displayed text separately from normalized fields.
- No quality score, confidence score, value metric, product ranking, or recommendation is calculated by the extension.
- No database or backend is required for this milestone.

## Initial extraction fields

- Listing/source: marketplace, product URL, extraction timestamp, extension version, page title, ASIN if present.
- Raw page text: title, brand/model/variant text, displayed price, rating, review count, availability, and available specification label/value pairs.
- Normalized smartphone fields: brand, model name/number, RAM (GB), storage (GB), display size (inches), battery capacity (mAh), operating system, 5G support, price (INR), rating, review count, availability.
- Validation: valid / needs_review / invalid, identity status, warnings, errors.

This is intentionally a small initial field set. Add fields only when there is a clear use case and a tested mapping from page text to normalized data.

## Acceptance criteria

1. The extension manifest uses Chromium Manifest V3.
2. The extension is limited to Amazon India pages and requests only permissions needed for the user-initiated extraction/export flow.
3. Clicking the extension on a supported smartphone listing extracts available fields and shows a preview before export.
4. The user can explicitly download one JSON record.
5. Exported JSON validates against the schema and includes schema version, source URL, UTC extraction timestamp, and extension version.
6. Raw text is preserved for extracted fields; normalized values are not silently substituted for raw values.
7. Missing data is represented as `null`; an unavailable price is never represented as zero.
8. RAM/storage variants are not merged merely because their product titles are similar.
9. If the page is unsupported, extraction fails, or identity is ambiguous, the extension shows a clear status and does not claim successful identification.
10. The extension performs no scoring, recommendation, automatic crawling, login-cookie access, or collection of personal browsing history.
11. At least 10 manually checked smartphone listings are used for validation, including multiple RAM/storage variants and missing-field cases.
12. The extraction logic is separated from JSON formatting so future adapters and backend integration do not require rewriting the extraction rules.

## Implementation order

1. Inspect the current repository and existing extension/docs before editing; preserve existing conventions and Git history.
2. Review and approve this schema and acceptance criteria.
3. Implement the smallest MV3 extension: manifest, content extraction module, popup/preview, schema validation, and explicit JSON download.
4. Add fixture-based tests for normalization, missing values, variant ambiguity, and JSON output.
5. Manually test against 10â€“20 permitted, user-opened product pages.
6. Only after extraction is reliable, build a local JSON importer; add FastAPI and database integration in a later milestone.

## Implementation constraints

- Do not start Docker Desktop or the full Compose stack for this milestone.
- Keep the extension lightweight for a 4 GB RAM Windows machine.
- Do not change PowerShell execution policy; use `npm.cmd` if npm commands are needed.
- Do not install unrelated packages or create backend/frontend scaffolds as part of this extension-only milestone.
- Do not treat successful extraction as proof that data collection or redistribution is permitted; confirm applicable marketplace terms and access rules before live use.
