# frontend

React + Vite + TypeScript web app. **No code yet.** Architecture: `../docs/CLIENTS_EVENTS_RELIABILITY.md` §2. API contract: `../docs/api/openapi.yaml`.

Must provide npm scripts `dev`, `build`, `lint`, `typecheck`, `test` (used by `Dockerfile` and CI). Rule: the UI renders API output only and never computes a score; show the three trust outputs separately.
