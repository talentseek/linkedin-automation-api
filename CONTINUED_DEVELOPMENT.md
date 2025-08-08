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
  - last_7_days: counts per day for invites/messages/replies
  - replies metrics: reply_count_last_n_days, reply_rate_last_n_days

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

1. Secure/gate debug endpoints in production (config flag or JWT). [DONE]
   - All debug routes now require JWT; removed reliance on DEBUG_ENDPOINTS_ENABLED for access control.
   - Enforce webhook signature when `UNIPILE_WEBHOOK_SECRET` is set (users & messaging).
   - Idempotency: ignore duplicate `message_received` by provider `message_id`.
2. Introduce DB migrations (Alembic/Flask-Migrate) and create migration for `conversation_id` (if missing).
   - Interim: Added JWT-protected `/api/admin/migrations/status` and `/api/admin/migrations/bootstrap` to safely ensure critical schema in prod.
3. Persist rate usage per day per account in DB for multi-instance accuracy. [NIGHTLY BACKFILL ADDED]
4. Parameterize snapshot endpoint by `campaign_id`/`name`. [DONE]
5. Add nightly job to backfill `conversation_id` for all connected leads. [DONE]
   - On-demand endpoints: `POST /api/admin/backfill/conversations`, `POST /api/admin/backfill/rate-usage` (JWT)
6. Enhance reply analytics: time-to-first-reply, reply distribution by step, and per-account reply rates.
7. Implement operator notifications for replies (e.g., email, Slack, or outbound webhook) with simple on/off config per environment.

---

## 7) Production Verification (2025-08-08)

- Webhooks:
  - Current state shows 2 webhooks via `GET /api/webhooks/list`:
    - `users` source (event `new_relation`) pointing to `/api/webhooks/unipile/users` (OK).
    - `messaging` source pointing to `/api/webhooks/unipile/users` (INCORRECT endpoint; should be `/api/webhooks/unipile/messaging`).
  - Action: Delete the misconfigured `messaging` webhook and recreate it with the correct request URL. Keep one webhook per source, covering all accounts.

- Campaign & Scheduler:
  - Campaign active and app healthy via `/api/webhooks/status`.
  - Scheduler auto-starts in production after code change to use resolved `config_name`; verified via `/api/webhooks/scheduler-status` → `scheduler_running=true`, `scheduler_thread_alive=true`.

- Historical Connection Sync:
  - `POST /api/webhooks/sync-historical-connections` found 9,369 relations for the connected account and matched 0 of 90 `invite_sent` leads.
  - Likely causes:
    - Relations often lack `public_identifier`; our loop currently skips when absent.
    - Lead `provider_id` may not be the LinkedIn `member_id` expected by relations.
    - Scope limited to `invite_sent` may miss already advanced leads.
  - Action: See “Historical sync matching” action items below.

- Analytics Endpoints (JWT):
  - Endpoints in place but require a production JWT. Current local token failed signature verification (different `JWT_SECRET_KEY`).
  - Action: Generate a prod JWT via `/api/auth/login` and retest `summary`, `timeseries`, and `rate-usage`.

### Action Items

- Webhooks:
  - Delete misconfigured `messaging` webhook and recreate with request URL `/api/webhooks/unipile/messaging`.
  - Maintain a single webhook per source (users, messaging) that covers all accounts.

- Scheduler visibility:
  - Align `/api/automation/scheduler/status` to mirror `thread`/`running` flags used by `/api/webhooks/scheduler-status`.

- Historical sync matching:
  - [DONE] Do not skip relations without `public_identifier`; use `member_id` to fetch profile via `get_user_profile_by_member_id` and derive `public_identifier`.
  - [DONE] Broaden lead scope to include `invited`/`pending_invite`/`connected`/`messaged`/`responded` when performing historical reconciliation.
  - [DONE] Add detailed logs for unmatched relations (`member_id`, `public_identifier`, attempted matches) and return a sample of unmatched entries for inspection.
  - [DONE] Count a lead as synced on identifier match even if `conversation_id` cannot be resolved yet; keep attempting to resolve chat id later.
  - Accept optional `campaign_id` and `linkedin_account_id` params to explicitly scope the sync.

- Debug operations:
  - Temporarily enable `DEBUG_ENDPOINTS_ENABLED=true` in production to use `/api/webhooks/get-conversation-ids` and `/api/webhooks/debug/send-chat`, then disable after checks.



## 8) Unipile Alignment Audit (Docs Cross-check)

- Webhooks (per docs):
  - A single webhook per source (e.g., `users`, `messaging`) can cover all accounts (`account_ids: []`). Our current setup matches this.
  - Must return HTTP 200 within 30s; Unipile retries up to 5 times on non-200. Our handlers return quickly; keep heavy work async.
  - Authentication: Unipile supports adding a custom secret header and verifying signature. We compute/validate `X-Unipile-Signature` when a secret is configured; keep secret optional in prod.
  - Headers: When creating via API, explicitly set `Content-Type: application/json` (we do).
  - Action: Fix `messaging` webhook `request_url` to `/api/webhooks/unipile/messaging` (currently mis-pointing to `/users`). Ensure events include: `message_received`, `message_read`, `message_reaction`, `message_edited`, `message_deleted`.

- Users/Relations:
  - Endpoint: `GET /api/v1/users/relations?account_id=...&cursor=...&limit=...` with pagination. We implemented cursor+limit and iterate until no cursor (OK).
  - Fields: relations may include `member_id` and may lack `public_identifier`.
  - Action: In historical sync, do NOT skip when `public_identifier` missing. Use `member_id` to fetch profile (`GET /api/v1/users/{member_id}?account_id=...`) and derive `public_identifier` to match and backfill lead fields.

- Profiles:
  - Endpoint: `GET /api/v1/users/{identifier}?account_id=...` where identifier can be `public_identifier` or LinkedIn `member_id`. We have both `get_user_profile` and `get_user_profile_by_member_id` (OK).

- Chats (Conversations):
  - Primary list: `GET /api/v1/chats?account_id=...&cursor=...&limit=...` (paginated). We call `/api/v1/chats` but do not page; add pagination support and fall back to legacy endpoints only on 404/5xx.
  - Participants: responses may expose `participants` or `attendees` with participant `provider_id`/`attendee_provider_id`. Our finder checks both (OK).
  - Single chat fetch: `GET /api/v1/chats/{chat_id}` available; we currently don't use (optional).

- Start 1:1 chat:
  - Endpoint: `POST /api/v1/chats` using multipart form. We send `account_id`, `attendees_ids`, `text`, and `linkedin[api]=classic`.
  - Docs frequently use an array parameter (e.g., `attendees_ids[]`) for multiple recipients. Action: Confirm whether `attendees_ids` vs `attendees_ids[]` is required; adjust to send array-compatible form when multiple values are needed.
  - Field names: creation uses `text` for message content; our production results confirm success with `text` (OK).

- Send message in an existing chat:
  - Endpoint: `POST /api/v1/chats/{chat_id}/messages` using multipart. Field `text` used for content. We do this and fallback to legacy JSON (`message`) if needed (OK).

- Webhook payloads:
  - `users:new_relation` payload includes `account_id`, `user_provider_id`, optionally `user_public_identifier`.
  - Action: In `handle_new_relation_event`, also match/update leads by `user_public_identifier` when present, and backfill `Lead.public_identifier` to improve future matches.

- Messaging webhooks:
  - Events include `message_received`, `message_read`, `message_reaction`, `message_edited`, `message_deleted`.
  - Action: Implement `message_received` handling: persist event, set lead status to `responded`, increment analytics/reply counters.

- Base URL:
  - Default documented base is `https://api.unipile.com/v1`. We use a cluster base (`UNIPILE_API_BASE_URL=https://api3.unipile.com:13359`) in production; keep this configurable and consistent across environments.


### Concrete Actions (Unipile Alignment)

1) Webhooks hygiene
- [DONE] Added `POST /api/webhooks/webhooks/fix-messaging` to auto-delete misconfigured messaging webhooks and create one pointing to `/api/webhooks/unipile/messaging` with standard events.
- [DONE] Executed in production; old ID removed and new created.
- [DONE] JWT-protected admin endpoints: `/api/webhooks/register`, `/api/webhooks/list`, `/api/webhooks/delete/{id}`, `/api/webhooks/webhooks/fix-messaging` now require JWT.
- Keep `users` webhook on `/api/webhooks/unipile/users`.
- Ensure both are configured with `Content-Type: application/json` and optional secret header.

2) Historical sync improvements
- [DONE] Use `member_id` to fetch profile when `public_identifier` missing; backfill `Lead.public_identifier` and match leads.
- [DONE] Expand scope beyond `invite_sent` to include `invited`/`pending_invite`/`connected` when reconciling.
- [DONE] Add optional `campaign_id` and `linkedin_account_id` body params to target specific scopes.
- [DONE] Return a small sample of unmatched relations with `member_id`/`public_identifier` for inspection in the response.

3) Chats pagination and robustness
- [DONE] Added pagination via `UnipileClient.get_all_chats` and updated `find_conversation_with_provider` to scan all pages.
- Only fall back to legacy conversation endpoints on clear 404/5xx from `/api/v1/chats`.

4) Event handling and analytics
- [DONE] `message_received` webhook processing persists events and marks leads as `responded` (handler present and wired).
- [DONE] Halt automation on reply: Scheduler processes only `pending_invite`/`connected`, so `responded` leads are excluded and will not continue in the sequence.
- Next: include reply metrics in analytics summary.
- Ensure idempotency by ignoring duplicate event IDs (if present) or by deduping on `(event_type, message_id)`.

5) Signature verification
- Keep signature verification enabled when `UNIPILE_WEBHOOK_SECRET` is set; respond 401 on invalid signatures outside debug environments.

