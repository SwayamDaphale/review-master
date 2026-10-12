# extension

Chromium Manifest V3 browser extension (content script, service worker, side panel), built with Vite. **No code yet.** Architecture: `../docs/CLIENTS_EVENTS_RELIABILITY.md` §1.

Must provide npm script `build` and `scripts/check-permissions.mjs` (CI permission gate: host permissions limited to the V1 marketplace and the Review Master API; no cookies, history or broad `<all_urls>` access).
