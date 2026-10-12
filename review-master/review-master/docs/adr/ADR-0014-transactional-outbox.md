# ADR-0014: Events use a transactional outbox

- **Status:** Accepted
- **Date:** 2026-10-10

## Context
Events (evaluation updated, price changed, webhooks) must not be lost or emitted for rolled-back changes.

## Decision
Events are inserted into `ops.event_outbox` in the same transaction as the change; a dispatcher publishes to consumers and webhook deliveries; consumers dedupe on `event_id`.

## Consequences
At-least-once delivery without a broker dependency in V1. Consumers must be idempotent; the dispatcher needs monitoring.

## Alternatives considered
Direct publish after commit (rejected: lost-event window); Kafka (rejected for V1: unnecessary operational weight).
