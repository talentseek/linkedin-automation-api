## LinkedIn Automation API – Final Sprint Plan

Status: In Progress
Owner: Team
Last Updated: 2025-08-20

### Guiding Principles
- OpenAPI-first: keep `docs/openapi.yaml` in sync with the live API at every change.
- Test-first: add or update tests alongside each change (unit, integration, and E2E where applicable).
- Production-safety: validate in local and staging before touching production.
- Source of truth for Unipile: `https://developer.unipile.com/docs` (reference specific sections per task).

### References
- Unipile Docs (root): https://developer.unipile.com/docs
- Webhooks (general): https://developer.unipile.com/docs (see “Webhooks” / “Events”)
- Users/Relations: https://developer.unipile.com/docs (see “Users” / “Relations”)
- Messaging/Chats: https://developer.unipile.com/docs (see “Messaging” / “Chats”)

> Note: Always cross-check endpoint shapes, pagination models, and authentication headers against the Unipile docs above before coding.

---

## Milestone 1 — Foundation Fixes (Webhooks, Connection Detection, Schema) ✅ COMPLETE

### Definition of Done ✅ ACHIEVED
1) ✅ Webhooks: receiving real events in production; events persisted; errors observable; replay/debug tools available.
2) ✅ Connection Detection: leads move from invite_sent → connected based on relations or webhook events; no hard-coded polling on non-existent endpoints.
3) ✅ Schema: verified columns, indexes, and migrations in place and reversible.

### Tasks ✅ ALL COMPLETED
- [x] [M1] Verify Unipile webhook registration (list and validate active webhooks)
- [x] [M1] Test webhook endpoints with real Unipile events (users + messaging sources)
- [x] [M1] Implement proper webhook signature verification (per Unipile guidance)
- [x] [M1] Add webhook health monitoring endpoint and metrics
- [x] [M1] Fix `handle_new_relation_webhook` for connection acceptance → updates lead + creates event
- [x] [M1] Fix `handle_message_received_webhook` for replies → creates/updates conversation + event
- [x] [M1] Add structured errors/logging in webhook handlers
- [x] [M1] Create webhook simulation + replay endpoints (dev-only)
- [x] [M1] Research correct Unipile endpoints for connections/relations (Users/Relations)
- [x] [M1] Implement connection detection via relations (paginated) instead of non-existent invitations endpoint
- [x] [M1] Add fallback: periodic relation backfill job + manual admin trigger
- [x] [M1] Create admin tools: manual status update to recover stuck leads (audited)
- [x] [M1] Add connection status monitoring/alerts (counts per day, acceptances)
- [x] [M1] Database schema audit: verify tables/columns, FKs, indexes, nullability
- [x] [M1] Create idempotent migrations and schema version tracking; add rollback scripts
- [x] [M1] Update OpenAPI (`/webhooks/*`, `/admin/*`) and add integration tests

**Status**: ✅ COMPLETE - See `MILESTONE_1_COMPLETION_REPORT.md` for detailed documentation

— Unipile references: Webhooks (events payloads), Users/Relations (acceptance detection), Auth headers.

---

## Milestone 2 — Scheduler & Sequence Engine Overhaul ✅ COMPLETE

### Definition of Done
1) Scheduler reliably advances leads across all steps honoring working hours, delays, and rate limits.
2) Sequence engine executes actions atomically; failures are retried with backoff; events persisted.
3) Full observability (structured logs, metrics, dashboards) for steps and rate usage.

### Tasks
- [x] [M2] Fix `_is_lead_ready_for_processing` (statuses, delays per step, rate-limit checks)
- [x] [M2] Fix `_process_single_lead` (refresh, execute, advance step, persist, emit event)
- [x] [M2] Implement retry with jitter + circuit breakers for Unipile calls
- [x] [M2] Validate and compute step delays; make timezone-safe; respect working hours
- [x] [M2] Step validation (required fields, action_type, message templates)
- [x] [M2] Personalization tokens: strict validation + preview util
- [x] [M2] Rate limits: persist daily counts; admin visibility; auto-reset
- [x] [M2] Structured logging and metrics for each step execution
- [x] [M2] Update OpenAPI for scheduler/admin endpoints; add E2E tests

**Status**: ✅ COMPLETE - Connection detection fixed, system fully functional for lead progression

— Unipile references: Messaging/Chats (send message; start chat vs send to chat), Users (profile IDs).

---

## Milestone 3 — Unipile & LinkedIn Integration Alignment ✅ COMPLETE

### Definition of Done ✅ ACHIEVED
1) ✅ All Unipile endpoints used are verified, version-aligned, and feature-flagged where needed.
2) ✅ OAuth/auth flow is resilient with refresh; errors observable.
3) ✅ Messaging uses conversations/chats per Unipile guidance; conversation_id persisted.

### Tasks ✅ ALL COMPLETED
- [x] [M3] Audit every Unipile call; replace deprecated/invalid endpoints
- [x] [M3] Add API version compatibility + graceful fallbacks
- [x] [M3] OAuth flow hardening (token refresh, expiry handling, storage)
- [x] [M3] Rate limit handling: backoff, headers/usage introspection, alerts
- [x] [M3] Connection request sending aligned to Unipile documented models
- [x] [M3] Conversation management: resolve user → chat, persist `conversation_id`
- [x] [M3] Message validation/sanitization; attachment handling (if needed)
- [x] [M3] Profile retrieval and normalization; light caching
- [x] [M3] Resend notifications hardening; templates; retry queue
- [x] [M3] Analytics counters for invites/messages/replies/connections
- [x] [M3] Update OpenAPI + integration tests for Unipile flows

**Status**: ✅ COMPLETE - All Unipile API endpoints fixed, LinkedIn operations working, external services operational

— Unipile references: Auth, Users (lookup/identifiers), Messaging (chats/messages), Rate limiting.

---

## Milestone 4 — Testing & Validation

### Definition of Done
1) 90%+ unit coverage in core modules; integration/E2E cover main flows.
2) Load/stress tested; SLA baselines documented.
3) OpenAPI spec is accurate and drives contract tests.

### Tasks
- [ ] [M4] Unit tests across routes/services/scheduler/sequence
- [ ] [M4] Integration tests for client/campaign/lead/webhook flows
- [ ] [M4] Contract tests from OpenAPI (request/response validation)
- [ ] [M4] E2E scenarios: import → activate → invite → connect → message → reply
- [ ] [M4] Load/stress/scalability tests; capture baselines
- [ ] [M4] Production readiness checklist; backup/restore drills
- [ ] [M4] Update all docs (OpenAPI, README, runbooks, troubleshooting)

---

## Milestone 5 — Deployment, Monitoring, and Operations

### Definition of Done
1) CI/CD with quality gates; rollback safety; staging parity.
2) Monitoring + alerting for app/DB/integrations.
3) Support/maintenance procedures formalized.

### Tasks
- [ ] [M5] CI/CD pipeline (build, test, deploy) with gates
- [ ] [M5] Staging env parity; deployment validation checks
- [ ] [M5] Rollback scripts and playbooks
- [ ] [M5] App/DB/infrastructure monitoring + dashboards
- [ ] [M5] Alert rules + notification channels + escalation
- [ ] [M5] Structured logging + log aggregation
- [ ] [M5] Backup/DR procedures and drills
- [ ] [M5] Support runbooks, SLAs, on-call

---

## Work Tracking

Use the checkboxes above. For each completed task, include:
- Link to PR and relevant code sections
- Link(s) to Unipile doc sections used
- Tests added/updated
- OpenAPI diffs
- Risk notes and rollout plan

Template snippet (copy per task):

```
- [ ] [Mx] <Task Title>
  - PR: <link>
  - Unipile refs: <link(s)>
  - Tests: <paths>
  - OpenAPI changes: <summary>
  - Notes: <risks/findings>
```


