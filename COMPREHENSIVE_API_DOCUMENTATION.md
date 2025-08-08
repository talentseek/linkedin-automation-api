# LinkedIn Automation API - Comprehensive Documentation

## Overview

The LinkedIn Automation API is a comprehensive backend system that integrates with the Unipile API to provide automated LinkedIn outreach capabilities for multi-tenant SaaS applications. This system enables businesses to manage clients, connect LinkedIn accounts, create outreach campaigns, and automate personalized messaging sequences while respecting LinkedIn's rate limits and best practices.

## Base URL

```
http://localhost:5000/api
```

## Authentication

The API uses JWT (JSON Web Token) authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

## API Endpoints

### Authentication

#### POST /auth/register
Register a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "John Doe"
}
```

**Response:**
```json
{
  "message": "User registered successfully",
  "user": {
    "id": "user_id",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

#### POST /auth/login
Authenticate and receive a JWT token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "jwt_token_here",
  "user": {
    "id": "user_id",
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

### Client Management

#### POST /clients
Create a new client.

**Request Body:**
```json
{
  "name": "Acme Corporation",
  "email": "contact@acme.com",
  "timezone": "America/New_York"
}
```

**Response:**
```json
{
  "message": "Client created successfully",
  "client": {
    "id": "client_id",
    "name": "Acme Corporation",
    "email": "contact@acme.com",
    "timezone": "America/New_York",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

#### GET /clients
Get all clients for the authenticated user.

**Response:**
```json
{
  "clients": [
    {
      "id": "client_id",
      "name": "Acme Corporation",
      "email": "contact@acme.com",
      "timezone": "America/New_York",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### GET /clients/{client_id}
Get a specific client by ID.

#### PUT /clients/{client_id}
Update a client.

#### DELETE /clients/{client_id}
Delete a client.

### LinkedIn Account Management

#### GET /clients/{client_id}/linkedin-accounts
Get all LinkedIn accounts for a client.

**Response:**
```json
{
  "linkedin_accounts": [
    {
      "id": "account_id",
      "client_id": "client_id",
      "account_id": "unipile_account_id",
      "email": "linkedin@example.com",
      "status": "connected",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### GET /linkedin-accounts/{account_id}
Get a specific LinkedIn account by ID.

#### PUT /linkedin-accounts/{account_id}
Update a LinkedIn account.

#### DELETE /linkedin-accounts/{account_id}
Delete a LinkedIn account.

### Unipile Integration

#### POST /unipile/auth/start
Start the Unipile hosted authentication flow.

**Request Body:**
```json
{
  "client_id": "client_id",
  "provider": "linkedin"
}
```

**Response:**
```json
{
  "auth_url": "https://unipile.com/auth/...",
  "message": "Redirect user to auth_url to complete authentication"
}
```

#### POST /unipile/auth/callback
Handle the callback from Unipile authentication.

**Request Body:**
```json
{
  "code": "auth_code_from_unipile",
  "state": "state_parameter"
}
```

### Campaign Management

#### POST /clients/{client_id}/campaigns
Create a new campaign for a client.

**Request Body:**
```json
{
  "name": "Q1 Outreach Campaign",
  "timezone": "America/New_York",
  "status": "draft"
}
```

**Response:**
```json
{
  "message": "Campaign created successfully",
  "campaign": {
    "id": "campaign_id",
    "client_id": "client_id",
    "name": "Q1 Outreach Campaign",
    "timezone": "America/New_York",
    "status": "draft",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

#### GET /clients/{client_id}/campaigns
Get all campaigns for a client.

#### GET /campaigns/{campaign_id}
Get a specific campaign by ID.

#### PUT /campaigns/{campaign_id}
Update a campaign.

#### DELETE /campaigns/{campaign_id}
Delete a campaign.

#### GET /campaigns/{campaign_id}/leads
Get all leads for a campaign.

### Lead Management

#### POST /campaigns/{campaign_id}/leads
Create a new lead for a campaign.

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "company_name": "Example Corp",
  "public_identifier": "john-doe-123",
  "status": "pending_invite"
}
```

#### POST /campaigns/{campaign_id}/leads/import
Import leads from LinkedIn Sales Navigator search.

**Request Body:**
```json
{
  "account_id": "linkedin_account_id",
  "search_params": {
    "keywords": "software engineer",
    "location": "San Francisco"
  }
}
```

**Response:**
```json
{
  "message": "Successfully imported 10 leads from Sales Navigator search",
  "imported_leads": [...],
  "duplicates_skipped": [
    {
      "public_identifier": "john-doe-123",
      "name": "John Doe",
      "existing_lead_id": "lead_id",
      "existing_status": "pending_invite"
    }
  ],
  "duplicates_across_campaigns": [
    {
      "public_identifier": "jane-smith-456",
      "name": "Jane Smith",
      "existing_campaigns": [
        {
          "campaign_id": "other_campaign_id",
          "campaign_name": "Q1 Outreach",
          "lead_status": "connected"
        }
      ]
    }
  ],
  "summary": {
    "total_profiles_found": 15,
    "new_leads_imported": 10,
    "duplicates_in_campaign": 3,
    "duplicates_across_campaigns": 2,
    "errors": 0
  }
}
```

#### POST /campaigns/{campaign_id}/leads/import-from-url
Import leads from a LinkedIn Sales Navigator URL.

**Request Body:**
```json
{
  "sales_navigator_url": "https://www.linkedin.com/sales/search/people?...",
  "account_id": "linkedin_account_id"
}
```

**Response:**
```json
{
  "message": "Successfully imported 10 leads from Sales Navigator URL",
  "imported_leads": [...],
  "duplicates_skipped": [
    {
      "public_identifier": "john-doe-123",
      "name": "John Doe",
      "existing_lead_id": "lead_id",
      "existing_status": "pending_invite"
    }
  ],
  "duplicates_across_campaigns": [
    {
      "public_identifier": "jane-smith-456",
      "name": "Jane Smith",
      "existing_campaigns": [
        {
          "campaign_id": "other_campaign_id",
          "campaign_name": "Q1 Outreach",
          "lead_status": "connected"
        }
      ]
    }
  ],
  "summary": {
    "total_profiles_found": 15,
    "new_leads_imported": 10,
    "duplicates_in_campaign": 3,
    "duplicates_across_campaigns": 2,
    "errors": 0
  },
  "url_used": "https://www.linkedin.com/sales/search/people?..."
}
```

#### POST /campaigns/{campaign_id}/leads/check-duplicates
Check for potential duplicates before importing leads.

**Request Body:**
```json
{
  "public_identifiers": ["john-doe-123", "jane-smith-456", "new-profile-789"]
}
```

**Response:**
```json
{
  "campaign_id": "campaign_id",
  "total_checked": 3,
  "new_profiles": ["new-profile-789"],
  "duplicates_in_campaign": [
    {
      "public_identifier": "john-doe-123",
      "existing_lead_id": "lead_id",
      "existing_status": "pending_invite"
    }
  ],
  "duplicates_across_campaigns": [
    {
      "public_identifier": "jane-smith-456",
      "existing_campaigns": [
        {
          "campaign_id": "other_campaign_id",
          "campaign_name": "Q1 Outreach",
          "lead_status": "connected"
        }
      ]
    }
  ],
  "summary": {
    "new_profiles_count": 1,
    "duplicates_in_campaign_count": 1,
    "duplicates_across_campaigns_count": 1
  }
}
```

#### POST /campaigns/{campaign_id}/leads/search
Perform advanced LinkedIn search using Sales Navigator parameters with pagination support.

**Request Body:**
```json
{
  "account_id": "linkedin_account_id",
  "search_config": {
    "api": "sales_navigator",
    "category": "people",
    "keywords": "software engineer",
    "location": {
      "include": ["102277331"]
    },
    "tenure": [
      {
        "min": 3
      }
    ],
    "company_headcount": [
      {
        "min": 51,
        "max": 200
      }
    ],
    "seniority": {
      "include": ["senior", "director"]
    }
  },
  "max_pages": 1,
  "page_limit": 10,
  "start": 0
}
```

**Pagination Parameters**:
- `max_pages` (optional): Maximum pages to fetch (default: 1 for preview)
- `page_limit` (optional): Results per page (default: 10)
- `start` (optional): Starting position (default: 0)

**Response:**
```json
{
  "message": "Search completed successfully",
  "search_results": {
    "items": [
      {
        "type": "PEOPLE",
        "id": "ACwAAAh-eI0BaIUD6d3gHWfitLZVmkij2aK1mxA",
        "name": "Sumanyu Sharma",
        "first_name": "Sumanyu",
        "last_name": "Sharma",
        "public_identifier": "sumanyusharma",
        "headline": "Co-Founder & CEO @ Hamming AI",
        "location": "San Francisco, California, United States",
        "current_positions": [
          {
            "company": "Hamming AI",
            "role": "Co-Founder & CEO",
            "location": "San Francisco, California, United States"
          }
        ]
      }
    ],
    "paging": {
      "total_count": 83087,
      "page_count": 10,
      "start": 0
    }
  },
  "campaign_id": "campaign_id",
  "total_results": 83087,
  "current_page": {
    "start": 0,
    "limit": 10,
    "count": 10
  },
  "pagination_info": {
    "total_count": 83087,
    "current_page_count": 10,
    "has_more": true,
    "next_start": 10
  }
}
```

## POST /campaigns/{campaign_id}/leads/search-and-import

**Description**: Perform advanced LinkedIn search and import results as leads with duplication management and pagination support.

**Request Body**:
```json
{
  "account_id": "linkedin-account-id",
  "search_config": {
    "api": "sales_navigator",
    "category": "people",
    "keywords": "CFO",
    "location": {
      "include": ["102257491"]
    },
    "seniority": {
      "include": ["cxo", "vice_president", "director"]
    },
    "company_headcount": [
      {
        "min": 51,
        "max": 200
      }
    ]
  },
  "max_pages": 5,
  "max_leads": 100,
  "page_limit": 10
}
```

**Pagination Parameters**:
- `max_pages` (optional): Maximum number of pages to process (default: 5)
- `max_leads` (optional): Maximum number of leads to import (default: 100)
- `page_limit` (optional): Results per page (default: 10, Unipile API default)

**Response**:
```json
{
  "message": "Successfully imported 8 leads from advanced search across 2 pages",
  "imported_leads": [
    {
      "campaign_id": "campaign-id",
      "first_name": "John",
      "last_name": "Doe",
      "company_name": "Example Corp",
      "public_identifier": "john-doe",
      "provider_id": "ACwAA...",
      "status": "pending_invite"
    }
  ],
  "total_imported": 8,
  "duplicates_skipped": [...],
  "duplicates_across_campaigns": [...],
  "summary": {
    "total_profiles_found": 20,
    "new_leads_imported": 8,
    "duplicates_in_campaign": 12,
    "duplicates_across_campaigns": 0,
    "errors": 0,
    "pages_processed": 2,
    "max_pages_requested": 5,
    "max_leads_requested": 100
  },
  "pagination_info": {
    "max_pages": 5,
    "max_leads": 100,
    "page_limit": 10,
    "pages_processed": 2
  },
  "search_config_used": {...},
  "errors": []
}
```

#### GET /search-parameters
Get available search parameters (locations, industries, skills, etc.) for building advanced searches.

**Request Body:**
```json
{
  "account_id": "linkedin_account_id",
  "type": "LOCATION",
  "keywords": "san francisco",
  "limit": 5
}
```

**Response:**
```json
{
  "message": "Search parameters retrieved successfully",
  "parameters": {
    "items": [
      {
        "id": "102277331",
        "object": "LinkedinSearchParameter",
        "title": "San Francisco, California, United States"
      },
      {
        "id": "90000084",
        "object": "LinkedinSearchParameter",
        "title": "San Francisco Bay Area"
      }
    ],
    "object": "LinkedinSearchParametersList",
    "paging": {
      "page_count": 5
    }
  },
  "param_type": "LOCATION",
  "keywords": "san francisco"
}
```

#### POST /campaigns/{campaign_id}/leads/merge-duplicates
Merge duplicate leads across campaigns for the same client.

**Request Body:**
```json
{
  "merge_strategy": "move"
}
```

**Merge Strategies:**
- `copy`: Copy leads from other campaigns to target campaign
- `move`: Move all duplicate data to target campaign and delete others
- `link`: Create references between campaigns (future enhancement)

**Response:**
```json
{
  "message": "Successfully processed 5 duplicate leads",
  "merged_leads": [
    {
      "public_identifier": "john-doe-123",
      "action": "merged",
      "target_campaign_id": "campaign_id",
      "duplicates_removed": 2
    }
  ],
  "skipped_leads": [
    {
      "public_identifier": "jane-smith-456",
      "reason": "Lead already exists in target campaign"
    }
  ],
  "summary": {
    "total_duplicates_found": 5,
    "successfully_merged": 3,
    "skipped": 2
  }
}
```

#### POST /leads/{lead_id}/convert-profile
Convert lead's public identifier to provider ID.

**Request Body:**
```json
{
  "account_id": "linkedin_account_id"
}
```

#### GET /leads/{lead_id}
Get a specific lead by ID.

#### PUT /leads/{lead_id}
Update a lead.

#### DELETE /leads/{lead_id}
Delete a lead.

### Sequence Management

#### PUT /campaigns/{campaign_id}/sequence
Update the sequence definition for a campaign.

**Request Body:**
```json
{
  "sequence": [
    {
      "step_order": 1,
      "action_type": "invite",
      "template": "Hi {first_name}, I'd love to connect with you and learn more about your work at {company_name}.",
      "delay_days": 0
    },
    {
      "step_order": 2,
      "action_type": "message",
      "template": "Thanks for connecting, {first_name}! I noticed your experience at {company_name}.",
      "delay_days": 2
    }
  ]
}
```

#### GET /campaigns/{campaign_id}/sequence
Get the sequence definition for a campaign.

#### GET /sequence/example
Get an example sequence definition.

#### GET /leads/{lead_id}/next-step
Get the next step in the sequence for a lead.

#### POST /leads/{lead_id}/execute-step
Execute the next step in the sequence for a lead.

**Request Body:**
```json
{
  "linkedin_account_id": "account_id"
}
```

#### POST /leads/{lead_id}/preview-step
Preview the personalized message for the next step.

#### POST /sequence/validate
Validate a sequence definition.

### Automation Management

#### POST /campaigns/{campaign_id}/start
Start automated outreach for a campaign.

**Response:**
```json
{
  "message": "Campaign automation started successfully",
  "campaign": {
    "id": "campaign_id",
    "status": "active"
  },
  "connected_accounts": 2
}
```

#### POST /campaigns/{campaign_id}/pause
Pause automated outreach for a campaign.

#### GET /campaigns/{campaign_id}/status
Get the automation status for a campaign.

**Response:**
```json
{
  "campaign_id": "campaign_id",
  "status": "active",
  "lead_statistics": {
    "pending_invite": 10,
    "invited": 5,
    "connected": 3,
    "responded": 1
  },
  "total_leads": 19,
  "scheduled_jobs": 8
}
```

#### GET /automation/rate-limits/{linkedin_account_id}
Get current rate limit status for a LinkedIn account.

**Response:**
```json
{
  "linkedin_account_id": "account_id",
  "daily_limits": {
    "invites": {
      "current": 15,
      "limit": 25,
      "remaining": 10
    },
    "messages": {
      "current": 45,
      "limit": 100,
      "remaining": 55
    }
  },
  "can_send_invite": true,
  "can_send_message": true
}
```

#### GET /automation/scheduler/status
Get the status of the background scheduler.

#### POST /automation/scheduler/start
Start the background scheduler.

#### POST /automation/scheduler/stop
Stop the background scheduler.

#### POST /leads/{lead_id}/schedule-step
Manually schedule the next step for a lead.

### Webhook Endpoints

#### POST /webhooks/unipile/users
Handle Unipile users webhook events (connection requests, profile views, etc.).

#### POST /webhooks/unipile/messaging
Handle Unipile messaging webhook events (messages received, etc.).

#### POST /webhooks/test
Test endpoint for webhook development and debugging.

Note:
- Single-webhook policy: ensure only one webhook (source `users`, event `new_relation`) is registered across all LinkedIn accounts. Use `GET /api/webhooks/list` and `DELETE /api/webhooks/delete/{id}` as needed.
- Scheduler status semantics (thread-based):
  - `/api/webhooks/scheduler-status` (no auth) exposes `scheduler_running` and `scheduler_thread_alive` from `running` and `thread.is_alive()`.
  - `/api/automation/scheduler/status` (JWT) returns `{ status, running, thread_alive }`.

### Analytics Endpoints

#### GET /api/analytics/campaigns/{campaign_id}/summary (JWT)
Returns campaign totals, status breakdown, last activity, and last-N-days invite/message counts.

#### GET /api/analytics/campaigns/{campaign_id}/timeseries?days=30 (JWT)
Returns per-day invites/messages/replies/connections over a given window.

#### GET /api/analytics/accounts/{linkedin_account_id}/rate-usage?days=7 (JWT)
Returns per-day invite/message usage for the account. Uses persisted usage when available; falls back to event aggregation.

### Messaging via Unipile Chats (LinkedIn)

To send LinkedIn messages reliably:

- List chats: `GET /api/v1/chats?account_id=...`
- Send into an existing chat: `POST /api/v1/chats/{chat_id}/messages` (multipart form, field `text`)
- Start a 1:1 chat and send: `POST /api/v1/chats` (multipart form) with fields:
  - `account_id`: Unipile account id
  - `attendees_ids`: LinkedIn user identifier (prefer `member_id`; fallback to `provider_id`)
  - `text`: message body
  - `linkedin[api]`: `classic`

The system resolves the attendee `member_id` via `/api/v1/users/{identifier}?account_id=...` before starting a chat and persists the returned `chat_id` as `conversation_id` on the lead.

### Scheduler & Delays

- Background loop every ~5 minutes
- Rate limits: invites/day 25, messages/day 100 (configurable)
- Working hours: 9–17 (configurable)
- Step delays (minutes): connection=0, first msg≈4320, second≈8640, third≈12960

#### GET /webhooks/status
Quick analytics (no auth): returns campaign id/name/status, total leads, lead_status_counts, and 10 most recent events.

#### POST /webhooks/sync-historical-connections
Backfills connections for the currently active campaign by matching Unipile relations with campaign leads and creating historical acceptance events.

#### POST /webhooks/get-conversation-ids
Attempts to resolve and persist chat ids for connected leads by scanning Unipile chats.

#### POST /webhooks/debug/send-chat
Debug utility to send to a single lead via Unipile Chats API. Resolves LinkedIn member_id, locates an existing chat or starts a new 1:1 chat, then sends the message. Returns raw provider response and method used.

## Data Models

### Client
```json
{
  "id": "string",
  "name": "string",
  "email": "string",
  "timezone": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### LinkedIn Account
```json
{
  "id": "string",
  "client_id": "string",
  "account_id": "string",
  "email": "string",
  "status": "connected|needs_reconnection|disabled|error",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Campaign
```json
{
  "id": "string",
  "client_id": "string",
  "name": "string",
  "timezone": "string",
  "sequence_json": "array",
  "status": "draft|active|paused|completed",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Lead
```json
{
  "id": "string",
  "campaign_id": "string",
  "first_name": "string",
  "last_name": "string",
  "company_name": "string",
  "public_identifier": "string",
  "provider_id": "string",
  "conversation_id": "string",
  "status": "pending_invite|invited|connected|responded|completed|error",
  "current_step": "integer",
  "last_step_sent_at": "datetime",
  "connected_at": "datetime",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Event
```json
{
  "id": "string",
  "lead_id": "string",
  "event_type": "string",
  "meta_json": "object",
  "created_at": "datetime"
}
```

## Sequence Definition

A sequence is an array of steps that define the outreach flow:

```json
[
  {
    "step_order": 1,
    "action_type": "invite",
    "template": "Hi {first_name}, I'd love to connect!",
    "delay_days": 0
  },
  {
    "step_order": 2,
    "action_type": "message",
    "template": "Thanks for connecting, {first_name}!",
    "delay_days": 2
  }
]
```

### Personalization Tokens

- `{first_name}`: Lead's first name
- `{last_name}`: Lead's last name
- `{full_name}`: Lead's full name
- `{company_name}`: Lead's company name

## Duplication Management

The LinkedIn Automation API includes comprehensive duplication management to prevent duplicate leads and ensure data integrity across campaigns.

### Database-Level Protection

- **Unique Constraint**: Each campaign enforces uniqueness on `public_identifier` to prevent duplicates within the same campaign
- **Automatic Prevention**: Database rejects duplicate entries at the constraint level

### Duplication Detection Types

#### 1. Campaign-Level Duplicates
- **Detection**: Same `public_identifier` within the same campaign
- **Action**: Automatically skipped during import
- **Reporting**: Included in `duplicates_skipped` array

#### 2. Cross-Campaign Duplicates
- **Detection**: Same `public_identifier` across different campaigns for the same client
- **Action**: Reported but still imported (configurable)
- **Reporting**: Included in `duplicates_across_campaigns` array

### Duplication Management Workflow

#### Step 1: Pre-Import Check
```bash
curl -X POST /api/campaigns/{campaign_id}/leads/check-duplicates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "public_identifiers": ["profile1", "profile2", "profile3"]
  }'
```

#### Step 2: Import with Duplication Reporting
```bash
curl -X POST /api/campaigns/{campaign_id}/leads/import-from-url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sales_navigator_url": "https://www.linkedin.com/sales/search/people?...",
    "account_id": "linkedin_account_id"
  }'
```

#### Step 3: Merge Duplicates (Optional)
```bash
curl -X POST /api/campaigns/{campaign_id}/leads/merge-duplicates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "merge_strategy": "move"
  }'
```

### Merge Strategies

#### Copy Strategy
- **Action**: Copy leads from other campaigns to target campaign
- **Use Case**: When you want to include leads in multiple campaigns
- **Result**: Creates new lead records in target campaign

#### Move Strategy
- **Action**: Move all duplicate data to target campaign and delete others
- **Use Case**: When you want to consolidate leads into a single campaign
- **Result**: Merges data and removes duplicate records

#### Link Strategy (Future)
- **Action**: Create references between campaigns
- **Use Case**: When you want to maintain relationships between campaigns
- **Result**: Links leads across campaigns without duplication

### Duplication Response Format

All import endpoints return detailed duplication information:

```json
{
  "message": "Successfully imported 10 leads",
  "imported_leads": [...],
  "duplicates_skipped": [
    {
      "public_identifier": "john-doe-123",
      "name": "John Doe",
      "existing_lead_id": "lead_id",
      "existing_status": "pending_invite"
    }
  ],
  "duplicates_across_campaigns": [
    {
      "public_identifier": "jane-smith-456",
      "name": "Jane Smith",
      "existing_campaigns": [
        {
          "campaign_id": "other_campaign_id",
          "campaign_name": "Q1 Outreach",
          "lead_status": "connected"
        }
      ]
    }
  ],
  "summary": {
    "total_profiles_found": 15,
    "new_leads_imported": 10,
    "duplicates_in_campaign": 3,
    "duplicates_across_campaigns": 2,
    "errors": 0
  }
}
```

### Best Practices

1. **Pre-Check Duplicates**: Use the check-duplicates endpoint before importing large lists
2. **Monitor Cross-Campaign Duplicates**: Review these to understand lead overlap across campaigns
3. **Regular Cleanup**: Use merge-duplicates to consolidate data periodically
4. **Respect Rate Limits**: Avoid importing the same leads multiple times to stay within LinkedIn's limits

## Error Responses

All endpoints return consistent error responses:

```json
{
  "error": "Error message description"
}
```

Common HTTP status codes:
- `400`: Bad Request - Invalid input data
- `401`: Unauthorized - Missing or invalid authentication
- `404`: Not Found - Resource not found
- `500`: Internal Server Error - Server-side error

## Rate Limiting

The system implements rate limiting to comply with LinkedIn's policies:

- **Connection Invitations**: 25 per day per account
- **Messages**: 100 per day per account
- **Working Hours**: 9 AM - 5 PM in the campaign's timezone
- **Randomized Delays**: 5-30 minutes between actions

## Webhook Events

### new_relation
Triggered when someone accepts a connection request.

### message_received
Triggered when someone replies to a message.

### account_status
Triggered when a LinkedIn account's connection status changes.

## Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///linkedin_automation.db

# JWT
JWT_SECRET_KEY=your_jwt_secret_key

# Unipile API
UNIPILE_API_KEY=your_unipile_api_key
UNIPILE_DSN=your_unipile_dsn
UNIPILE_WEBHOOK_SECRET=your_webhook_secret

# Rate Limiting
MAX_CONNECTIONS_PER_DAY=25
MIN_DELAY_BETWEEN_ACTIONS=300
MAX_DELAY_BETWEEN_ACTIONS=1800
WORKING_HOURS_START=9
WORKING_HOURS_END=17
```

## Getting Started

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run the Application**
   ```bash
   python src/main.py
   ```

4. **Access the API**
   ```
   http://localhost:5000/api
   ```

## Deployment

The application is designed to be deployed on any platform that supports Python Flask applications. Key considerations:

- Set `DEBUG=False` in production
- Use a production WSGI server like Gunicorn
- Configure a production database (PostgreSQL recommended)
- Set up proper logging and monitoring
- Ensure webhook endpoints are accessible from the internet

## Support

For technical support or questions about the API, please refer to the comprehensive documentation or contact the development team.

