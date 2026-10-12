# ADR-0009: React + Vite + TypeScript for the web app

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Same stack as the reference project; the app is an authenticated tool, not primarily a content site.

## Decision
Vite SPA served as static files behind nginx/CDN; TanStack Query for server state. The extension is also Vite-built TypeScript.

## Consequences
Fast development and shared types. A pure SPA is weaker for public SEO; if SEO pages become a goal, add a server-rendered public site later (open decision #8). `VITE_*` values are build-time: one build per environment or a runtime config.

## Alternatives considered
Next.js (capsule's example; better SEO/SSR, heavier; revisit with decision #8).
