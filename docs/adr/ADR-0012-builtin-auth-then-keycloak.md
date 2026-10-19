# ADR-0012: Built-in authentication first, behind an AuthProvider; Keycloak when enterprise SSO is needed

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
V1 needs sign-up/login, roles, MFA for privileged users and API keys. Enterprise SSO is a V2 commercial need.

## Decision
PostgreSQL `auth` schema, argon2id, JWT access + rotating refresh, TOTP, email verification, hashed API keys. `AuthProvider` abstraction. Keycloak (compose profile) can replace or federate later without changing the permission model.

## Consequences
No extra identity database or service in V1. Security-critical code must be well tested; swapping providers needs the abstraction kept clean.

## Alternatives considered
Auth0/Clerk/Cognito (viable managed options; weigh cost and data residency); Keycloak from day one (deferred: operational weight).
