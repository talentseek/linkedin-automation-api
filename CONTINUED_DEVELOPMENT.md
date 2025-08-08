# Continued Development Plan

This document tracks next steps, new endpoints to add, audit findings, and recommended improvements for the LinkedIn Automation API.

## 1) New Analytics Endpoints (Proposed)

Add a dedicated analytics surface beyond the existing snapshot endpoint (`GET /api/webhooks/status`).

### A. Campaign Summary
- Method: `GET /api/analytics/campaigns/{campaign_id}/summary`
- Auth: JWT
- Response:
  - campaign_id, name, status
  - totals: leads, invite_sent, connected, messaged, responded, completed
  - last_activity_at (max event.timestamp)
  - last_7_days: counts per day for invites/messages

### B. Campaign Time Series
- Method: `GET /api/analytics/campaigns/{campaign_id}/timeseries?days=30`
- Auth: JWT
- Response:
  - days: [ISO date]
  - invites_sent_per_day
  - messages_sent_per_day
  - replies_received_per_day (webhook `message_received`)

### C. Account Rate Utilization
- Method: `GET /api/analytics/accounts/{linkedin_account_id}/rate-usage?days=7`
- Auth: JWT
- Response:
  - invites_sent_per_day vs configured daily limit
  - messages_sent_per_day vs configured daily limit

Implementation notes:
- Backed by `Event` table aggregations; standardized event types are used: `connection_request_sent`, `message_sent`, `message_received`, `connection_accepted[_historical]`.
- Use database-side GROUP BY date(bucket) for performance.

## 2) Current Analytics Surfaces

- Snapshot (no auth): `GET /api/webhooks/status` → campaign totals, recent events (10). Useful for quick checks.
- Automation status (JWT): `GET /api/automation/campaigns/{campaign_id}/status` → per-status counts for the campaign.

## 3) Codebase Audit (Findings & Actions)

### Messaging via Unipile Chats
- Status: Implemented chat-based sending with fallbacks.
- Key flows:
  - Resolve LinkedIn `member_id` via `/api/v1/users/{identifier}?account_id=...`.
  - Find chat by participant; if not found, start 1:1 chat and send.
  - Persist `conversation_id` (chat_id) on `Lead` for subsequent steps.
- Improvement: Add a scheduled backfill job to populate `conversation_id` for all `connected` leads once per day.

### Scheduler
- Status: Thread-based loop, runs every ~5 minutes, respects working hours and rate limits.
- Delays now computed off `last_step_sent_at` (correct); fallback to `created_at` only when necessary.
- Limitation: Daily counters are in-memory and reset on process restart.
  - Action: Consider persisting rate usage per account per day in DB for durability and multi-instance correctness.

### Webhooks & Debug Endpoints
- Multiple debug endpoints are exposed without auth (by design for current ops):
  - `GET /api/webhooks/status`, `GET /api/webhooks/debug-timing`, `POST /api/webhooks/debug/send-chat`, etc.
- Action: Gate these behind an environment flag (e.g., `DEBUG_ENDPOINTS_ENABLED`) or JWT in production.

### Database Migrations
- `conversation_id` was added via manual SQL.
- Action: Introduce Alembic/Flask-Migrate to track schema changes and generate repeatable migrations.

### Unipile Client
- Robust fallbacks added:
  - `get_conversations` → `/api/v1/chats` then legacy fallbacks
  - `send_message` → legacy conversation path then `/api/v1/chats/{chat_id}/messages` (multipart)
  - `start_chat_with_attendee` → multipart with `linkedin[api]=classic`
  - `find_conversation_with_provider` scans participants/attendees
- Minor tidy-up:
  - Remove redundant return after try/except in `send_message` (low priority, no functional impact).

### Campaign Name Assumption
- Snapshot endpoint currently ties analytics to `"Y Meadows Manufacturing Outreach"`.
- Action: Extend snapshot endpoint to accept `campaign_id` or `campaign_name` as a query parameter; default remains for convenience.

### Event Semantics & Consistency
- Event types used: `connection_request_sent`, `connection_accepted`, `connection_accepted_historical`, `message_sent`, `message_received`.
- Action: Document these centrally and ensure all producers include consistent `meta_json` keys (e.g., `linkedin_account_id`, `method`, `unipile_result`).

## 4) Endpoint Specs Implemented

Implemented and registered under `/api/analytics`:

```http
GET /api/analytics/campaigns/{campaign_id}/summary
GET /api/analytics/campaigns/{campaign_id}/timeseries?days=30
GET /api/analytics/accounts/{linkedin_account_id}/rate-usage?days=7
```

Auth: JWT. Role: standard user.

Notes:
- Aggregates are based on `Event` table. Event types used: `connection_request_sent`, `message_sent`, `message_received`, `connection_accepted`, `connection_accepted_historical`.
- Timeseries buckets by UTC day using `Event.timestamp`.

## 5) Operational Notes

- Rate Limits (from config): invites=25/day, messages=100/day. Working hours 9–17.
- Sequence delays (minutes): 0 / 4320 / 8640 / 12960 (approx. 3/6/9 working days).
- Chats API requires multipart form and LinkedIn `member_id` when possible.

## 6) Backlog (Prioritized)

1. Secure/gate debug endpoints in production (config flag or JWT).
2. Introduce DB migrations (Alembic/Flask-Migrate) and create migration for `conversation_id` (if missing).
3. Persist rate usage per day per account in DB for multi-instance accuracy.
4. Parameterize snapshot endpoint by `campaign_id`/`name`.
5. Add nightly job to backfill `conversation_id` for all connected leads.
6. Add replies tracking to analytics (reply counts and reply rate) and surface in summary endpoint once `message_received` webhooks arrive.


