# Review Master web app

React 18, Vite, TypeScript, React Router and TanStack Query. Plain CSS with a light and dark theme.
It contains the public landing page, the web app (explore, product, compare, saved, import, account) and a separate admin area.

There is **no backend and no database yet**. The app runs on a typed mock API with sample data, and keeps saved items, settings and the admin audit log in the browser (`localStorage`). Every screen that shows sample data says so.

## Run it

```bash
cd frontend
cp .env.example .env.local      # optional, see below
npm install                     # creates package-lock.json: commit it (CI uses `npm ci`)
npm run dev                     # http://localhost:5173
```

| Script | What it does |
|---|---|
| `npm run dev` | Dev server |
| `npm run build` | Type-check, then production build into `dist/` |
| `npm run typecheck` | `tsc --noEmit` (strict) |
| `npm run lint` | ESLint |
| `npm test` | Vitest (jsdom + Testing Library) |

## Pages

| Route | Purpose | Sign-in |
|---|---|---|
| `/` | Landing page | none |
| `/extension` | How to install and use the browser extension | none |
| `/login`, `/signup` | Google sign-in (one flow for both) | none |
| `/app` | Explore and search (name, Amazon India link or ASIN) | none |
| `/app/products/:id?v=<variant>` | Score, confidence, evidence, community, expert, price | none |
| `/app/compare?ids=a,b,c` | Side-by-side comparison, same category only | none |
| `/app/import` | Paste the extension's JSON and see how it matches | none |
| `/app/saved`, `/app/account` | Saved products, price alerts, profile, theme | Google or demo |
| `/admin/login` | Admin sign-in (dummy password) | admin password |
| `/admin` | Overview, catalogue and match queue, evaluation models, moderation, users and roles, site settings, audit log | admin password |

## Google sign-in

The app uses Google Identity Services. To switch it on:

1. In Google Cloud Console, open **APIs and Services, Credentials, Create credentials, OAuth client ID**, type **Web application**.
2. Add `http://localhost:5173` under **Authorized JavaScript origins** (add your real domain later).
3. Copy the client ID into `frontend/.env.local` as `VITE_GOOGLE_CLIENT_ID=...` and restart `npm run dev`.

Without a client ID the sign-in page offers a **demo account** instead, so everything stays usable.

> **Important.** Today the browser decodes Google's ID token and trusts it. That is fine for a demo, but it is not real authentication: anyone could forge it. When the backend exists it must verify the token's signature and audience (`POST /api/v1/auth/google`) and issue its own session. See `architecture/adr/ADR-0018-google-sign-in.md`.

## Admin area

The admin password is `admin123` unless `VITE_ADMIN_PASSWORD` is set. It is checked **in the browser** and is visible in the built JavaScript, so it protects nothing real. It only lets the admin screens be built before the backend has real admin sign-in. Do not deploy it publicly.

What the admin area demonstrates (all stored in this browser for now):
- Site settings that change the live site: announcement banner, maintenance mode, sample-data notice, feature switches.
- An evaluation model screen that refuses to publish until every weight is set, the weights add up to 1.00 and both approvals are ticked. Published versions lock.
- A match queue (probable and ambiguous product matches confirmed by a person), moderation queue, role changes (nobody can change their own role) and an audit log of every action.

## Rules the interface follows

These come from the architecture (`architecture/`) and are covered by tests:

1. **The UI never computes a score.** It displays what the API returns. The only conversion is the 0 to 100 API scale shown as 0 to 10 (`lib/format.ts`).
2. **Three outputs stay separate:** the Review Master score with its confidence, community feedback with review-pattern signals, and expert assessment. Price sits beside them, not inside the score.
3. **Missing data is never zero.** It shows as "Not scored" or "Not captured", and an insufficient-evidence result withholds the overall score.
4. **AI text is labelled.** An AI summary carries an "AI grounded summary" label. A template summary says it was not written by AI.
5. **Review-pattern signals are hints, not verdicts.** The UI never calls a review or reviewer "fake".
6. **Cross-category comparisons are blocked**, with an explanation.

## Where things are

```
src/
  api/        ApiClient contract, mock API, sample data (swap for the real /api/v1 client in api/index.ts)
  auth/       Google Identity Services helpers, route guards
  components/ evidence meter, score ring, badges, parameter list, price chart, search box, ...
  layouts/    public, app and admin layouts
  lib/        formatters, storage, identifier and extension-JSON parsing, admin gate, audit log
  pages/      landing, public, app and admin pages
  state/      theme, auth session, site settings, saved products and alerts
  styles/     tokens.css (light and dark), base.css, app.css
  types/      API types that mirror docs/api/openapi.yaml
```

## Connecting the real backend

1. Write a class that implements `ApiClient` (`src/api/client.ts`) and calls `/api/v1` using the shapes in `docs/api/openapi.yaml`.
2. Return it from `src/api/index.ts` instead of `mockApi`.
3. Replace `localStorage` for saved items and alerts with the `/api/v1/saved-products` and `/api/v1/price-alerts` endpoints, and settings with admin endpoints.
4. Replace the admin password gate with the backend's admin authentication.
5. Remove the sample-data notice setting once real evaluations are published.

## Testing and what has been verified

- 64 tests are included: format, identifier, extension-JSON, storage, Google-token, mock-API and admin-rule tests, component tests, and page-flow tests.
- When this was written the sandbox had no access to the npm registry, so `npm install`, `npm run lint` and `npm test` have **not been run** with the real packages. What was checked instead: a strict TypeScript type-check of all source against typed stand-ins for the four external libraries, the 46 pure-logic tests through a Vitest-compatible runner, and a 46-step walkthrough in headless Chromium (light, dark and a 390 px phone) that exercises the same flows as the page tests. If `npm install` or any script reports a problem, please send the output.
