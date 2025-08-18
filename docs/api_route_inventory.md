### API Route Inventory (Current → Proposed)

Note: Proposed paths adopt version prefix `/api/v1`, normalize resource naming, and fold campaign subresources under `/campaigns/{campaign_id}`.

#### Auth (prefix: /api/auth)
| Current | Proposed | Action |
|---|---|---|
| /api/auth/login | /api/v1/auth/login | keep (move/version) |
| /api/auth/refresh | /api/v1/auth/refresh | keep (move/version) |
| /api/auth/verify | — | deprecate or admin-only |

#### Clients (prefix: /api/clients)
| Current | Proposed | Action |
|---|---|---|
| /api/clients/clients | /api/v1/clients | keep (dedupe path) |
| /api/clients/clients/{client_id} | /api/v1/clients/{client_id} | keep (dedupe path) |

#### Campaigns (prefix: /api/campaigns, /api/automation)
| Current | Proposed | Action |
|---|---|---|
| /api/campaigns/clients/{client_id}/campaigns | /api/v1/campaigns?client_id=... | keep (flatten) |
| /api/campaigns/campaigns/{campaign_id} | /api/v1/campaigns/{campaign_id} | keep (dedupe path) |
| /api/campaigns/campaigns/{campaign_id}/leads | /api/v1/campaigns/{campaign_id}/leads | keep |
| /api/automation/campaigns/{campaign_id}/status | /api/v1/campaigns/{campaign_id}/status | keep (move) |
| /api/automation/campaigns/{campaign_id}/start | /api/v1/campaigns/{campaign_id}/actions/start | keep (move) |
| /api/automation/campaigns/{campaign_id}/pause | /api/v1/campaigns/{campaign_id}/actions/pause | keep (move) |

#### Sequence (prefix: /api/sequence)
| Current | Proposed | Action |
|---|---|---|
| /api/sequence/campaigns/{campaign_id}/sequence (GET/PUT) | /api/v1/campaigns/{campaign_id}/sequence | keep (move) |
| /api/sequence/campaigns/{campaign_id}/timezone (GET/PUT) | /api/v1/campaigns/{campaign_id}/timezone | keep (move) |
| /api/sequence/leads/{lead_id}/next-step | /api/v1/leads/{lead_id}/next-step | keep (optional) |
| /api/sequence/leads/{lead_id}/execute-step | /api/v1/leads/{lead_id}/execute-step | keep (optional) |
| /api/sequence/leads/{lead_id}/preview-step | /api/v1/leads/{lead_id}/preview-step | keep (optional) |
| /api/sequence/timezones | /api/v1/sequence/timezones | keep |
| /api/sequence/sequence/{validate|test-delays} | /api/v1/sequence/{validate|test-delays} | keep |

#### Leads (prefix: /api/leads)
| Current | Proposed | Action |
|---|---|---|
| /api/leads/campaigns/{campaign_id}/leads (GET/POST) | /api/v1/campaigns/{campaign_id}/leads | keep |
| /api/leads/leads/{lead_id} (GET/PUT/DELETE) | /api/v1/leads/{lead_id} | keep (dedupe path) |
| /api/leads/campaigns/{campaign_id}/leads/import[/-from-url] | /api/v1/campaigns/{campaign_id}/leads/import[/-from-url] | keep |
| /api/leads/campaigns/{campaign_id}/leads/search[|/smart-search] | /api/v1/campaigns/{campaign_id}/leads/search[|/smart-search] | keep |
| /api/leads/campaigns/{campaign_id}/leads/first-level-connections[/preview] | /api/v1/campaigns/{campaign_id}/leads/first-level-connections[/preview] | keep |
| /api/leads/campaigns/{campaign_id}/leads/check-duplicates | /api/v1/campaigns/{campaign_id}/leads/check-duplicates | keep |
| /api/leads/campaigns/{campaign_id}/leads/merge-duplicates | /api/v1/campaigns/{campaign_id}/leads/merge-duplicates | keep |
| /api/leads/leads/{lead_id}/convert-profile | /api/v1/leads/{lead_id}/convert-profile | keep |
| /api/leads/campaigns/{campaign_id}/leads/enrich-company | /api/v1/campaigns/{campaign_id}/leads/enrich-company | keep |
| /api/leads/search-parameters[|/helper] | /api/v1/leads/search-parameters[|/helper] | keep |

#### Analytics (prefix: /api/analytics)
| Current | Proposed | Action |
|---|---|---|
| /api/analytics/campaigns/{campaign_id}/{summary|timeseries} | /api/v1/campaigns/{campaign_id}/analytics/{summary|timeseries} | keep (move) |
| /api/analytics/accounts/{linkedin_account_id}/rate-usage | /api/v1/analytics/accounts/{linkedin_account_id}/rate-usage | keep |
| /api/analytics/campaigns/{campaign_id}/export/csv | /api/v1/analytics/campaigns/{campaign_id}/export/csv | keep |
| /api/analytics/real-time/activity | /api/v1/analytics/real-time/activity | keep |
| /api/analytics/clients/{client_id}/comparative-analytics | /api/v1/analytics/clients/{client_id}/comparative | keep (rename) |
| /api/analytics/comparative/campaigns | /api/v1/analytics/comparative/campaigns | keep |
| /api/analytics/weekly-stats/* | /api/v1/analytics/weekly-stats/* | keep |

#### Automation (prefix: /api/automation)
| Current | Proposed | Action |
|---|---|---|
| /api/automation/scheduler/{status|start|stop|weekend-status} | /api/v1/automation/scheduler/{status|start|stop|weekend-status} | keep |
| /api/automation/rate-limits/{linkedin_account_id} | /api/v1/automation/rate-limits/{linkedin_account_id} | keep |
| /api/automation/notifications/* | /api/v1/admin/notifications/* | admin-only or remove |
| /api/automation/test/* | /api/v1/admin/automation/test/* | admin-only or remove |

#### Webhooks (prefix: /api/webhooks)
| Current | Proposed | Action |
|---|---|---|
| /api/webhooks/unipile/{users|messaging} | /api/v1/webhooks/unipile/{users|messaging} | keep |
| /api/webhooks/status | /api/v1/webhooks/status | keep |
| /api/webhooks/webhook/health | /api/v1/webhooks/health | keep (rename) |
| /api/webhooks/webhook/data | /api/v1/admin/webhooks/data | admin-only |
| /api/webhooks/{list|register|delete/{id}|configure-unified} | /api/v1/admin/webhooks/{list|register|delete/{id}|configure-unified} | admin-only |
| /api/webhooks/unipile/test* | /api/v1/admin/webhooks/unipile/test* | admin-only or remove |

#### LinkedIn Accounts (prefix: /api/linkedin-accounts)
| Current | Proposed | Action |
|---|---|---|
| /api/linkedin-accounts/clients/{client_id}/linkedin-accounts | /api/v1/linkedin-accounts?client_id=... | keep (flatten) |
| /api/linkedin-accounts/linkedin-accounts/{account_id} | /api/v1/linkedin-accounts/{account_id} | keep (dedupe path) |

#### Users (prefix: /api/users)
| Current | Proposed | Action |
|---|---|---|
| /api/users/users | /api/v1/users | keep (dedupe path) |
| /api/users/users/{user_id} | /api/v1/users/{user_id} | keep (dedupe path) |

#### Admin (prefix: /api/admin)
| Current | Proposed | Action |
|---|---|---|
| /api/admin/migrations/status | /api/v1/admin/migrations/status | keep |
| /api/admin/migrations/bootstrap | /api/v1/admin/migrations/bootstrap | keep |
| /api/admin/backfill/{conversations|rate-usage} | /api/v1/admin/backfill/{conversations|rate-usage} | keep |


