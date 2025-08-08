# LinkedIn Automation API - Duplication Management Guide

## Overview

This guide covers the comprehensive duplication management system implemented in the LinkedIn Automation API. The system prevents duplicate leads, ensures data integrity, and provides tools for managing duplicates across campaigns.

## Table of Contents

1. [Why Duplication Management Matters](#why-duplication-management-matters)
2. [How the System Works](#how-the-system-works)
3. [Database-Level Protection](#database-level-protection)
4. [API Endpoints](#api-endpoints)
5. [Workflow Examples](#workflow-examples)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## Why Duplication Management Matters

### LinkedIn Compliance
- **Rate Limits**: LinkedIn has strict limits on connection requests and messages
- **Account Safety**: Duplicate outreach can trigger account restrictions
- **Professional Image**: Avoids appearing spammy to prospects

### Data Quality
- **Accurate Metrics**: Prevents inflated success rates from duplicate counting
- **Campaign Efficiency**: Focuses efforts on unique prospects
- **Resource Optimization**: Saves time and API calls

### Business Intelligence
- **Cross-Campaign Insights**: Understand lead overlap across campaigns
- **Performance Tracking**: Accurate attribution of results
- **Strategic Planning**: Better campaign targeting decisions

## How the System Works

### Duplication Detection Levels

#### 1. Campaign-Level Duplicates
- **Scope**: Within the same campaign
- **Detection**: Same `public_identifier` in the same campaign
- **Action**: Automatically skipped during import
- **Database**: Enforced by unique constraint

#### 2. Cross-Campaign Duplicates
- **Scope**: Across different campaigns for the same client
- **Detection**: Same `public_identifier` in different campaigns
- **Action**: Reported but still imported (configurable)
- **Use Case**: Understanding lead overlap across campaigns

### Duplication Response Structure

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

## Database-Level Protection

### Unique Constraints

The system enforces uniqueness at the database level:

```sql
-- Unique constraint on campaign_id + public_identifier
UNIQUE(campaign_id, public_identifier)
```

### Lead Model Enhancements

```python
class Lead(db.Model):
    # ... existing fields ...
    
    # Unique constraint to prevent duplicates within the same campaign
    __table_args__ = (
        UniqueConstraint('campaign_id', 'public_identifier', name='uq_campaign_public_identifier'),
    )
    
    @classmethod
    def find_duplicates_across_campaigns(cls, public_identifier: str, client_id: str = None):
        """Find all leads with the same public_identifier across campaigns."""
    
    @classmethod
    def find_duplicates_in_campaign(cls, public_identifier: str, campaign_id: str):
        """Find leads with the same public_identifier in a specific campaign."""
```

## API Endpoints

### 1. Advanced Search with Parameters

**Endpoint**: `POST /api/campaigns/{campaign_id}/leads/search`

**Purpose**: Perform advanced LinkedIn search using Sales Navigator parameters
**Use Case**: Build targeted searches with specific criteria

**Request**:
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
  }
}
```

**Response**:
```json
{
  "message": "Search completed successfully",
  "search_results": {
    "items": [
      {
        "type": "PEOPLE",
        "id": "ACwAAAh-eI0BaIUD6d3gHWfitLZVmkij2aK1mxA",
        "name": "Sumanyu Sharma",
        "public_identifier": "sumanyusharma",
        "headline": "Co-Founder & CEO @ Hamming AI",
        "location": "San Francisco, California, United States"
      }
    ],
    "paging": {
      "total_count": 83087,
      "page_count": 10,
      "start": 0
    }
  },
  "total_results": 83087
}
```

### 2. Search and Import with Duplication Management

**Endpoint**: `POST /api/campaigns/{campaign_id}/leads/search-and-import`

**Purpose**: Perform advanced search and import results with automatic duplication management
**Use Case**: One-step search and import with built-in duplicate prevention

**Request**:
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
    ]
  }
}
```

**Response**:
```json
{
  "message": "Successfully imported 10 leads from advanced search",
  "imported_leads": [...],
  "duplicates_skipped": [],
  "duplicates_across_campaigns": [],
  "summary": {
    "total_profiles_found": 10,
    "new_leads_imported": 10,
    "duplicates_in_campaign": 0,
    "duplicates_across_campaigns": 0,
    "errors": 0
  },
  "search_config_used": {
    "api": "sales_navigator",
    "category": "people",
    "keywords": "software engineer",
    "location": {
      "include": ["102277331"]
    }
  }
}
```

### 3. Get Search Parameters

**Endpoint**: `GET /api/search-parameters`

**Purpose**: Get available search parameters (locations, industries, skills, etc.)
**Use Case**: Build advanced search queries with correct parameter IDs

**Request**:
```json
{
  "account_id": "linkedin_account_id",
  "type": "LOCATION",
  "keywords": "san francisco",
  "limit": 5
}
```

**Response**:
```json
{
  "message": "Search parameters retrieved successfully",
  "parameters": {
    "items": [
      {
        "id": "102277331",
        "title": "San Francisco, California, United States"
      },
      {
        "id": "90000084",
        "title": "San Francisco Bay Area"
      }
    ]
  },
  "param_type": "LOCATION",
  "keywords": "san francisco"
}
```

### 4. Check Duplicates Before Import

**Endpoint**: `POST /api/campaigns/{campaign_id}/leads/check-duplicates`

**Purpose**: Pre-import duplicate detection

**Request**:
```json
{
  "public_identifiers": ["profile1", "profile2", "profile3"]
}
```

**Response**:
```json
{
  "campaign_id": "campaign_id",
  "total_checked": 3,
  "new_profiles": ["profile3"],
  "duplicates_in_campaign": [
    {
      "public_identifier": "profile1",
      "existing_lead_id": "lead_id",
      "existing_status": "pending_invite"
    }
  ],
  "duplicates_across_campaigns": [
    {
      "public_identifier": "profile2",
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

### 5. Import with Duplication Reporting

**Endpoint**: `POST /api/campaigns/{campaign_id}/leads/import-from-url`

**Purpose**: Import leads with automatic duplicate detection

**Request**:
```json
{
  "sales_navigator_url": "https://www.linkedin.com/sales/search/people?...",
  "account_id": "linkedin_account_id"
}
```

**Response**: Includes detailed duplication information (see structure above)

### 6. Merge Duplicates

**Endpoint**: `POST /api/campaigns/{campaign_id}/leads/merge-duplicates`

**Purpose**: Consolidate duplicate leads across campaigns

**Request**:
```json
{
  "merge_strategy": "move"
}
```

**Merge Strategies**:
- `copy`: Copy leads from other campaigns to target campaign
- `move`: Move all duplicate data to target campaign and delete others
- `link`: Create references between campaigns (future enhancement)

**Response**:
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

## Workflow Examples

### Example 1: Safe Import Workflow

```bash
# Step 1: Check for duplicates before importing
curl -X POST /api/campaigns/{campaign_id}/leads/check-duplicates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "public_identifiers": ["profile1", "profile2", "profile3"]
  }'

# Step 2: Import only new profiles
curl -X POST /api/campaigns/{campaign_id}/leads/import-from-url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sales_navigator_url": "https://www.linkedin.com/sales/search/people?...",
    "account_id": "linkedin_account_id"
  }'
```

### Example 2: Cross-Campaign Analysis

```bash
# Import leads and analyze cross-campaign duplicates
curl -X POST /api/campaigns/{campaign_id}/leads/import-from-url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sales_navigator_url": "https://www.linkedin.com/sales/search/people?...",
    "account_id": "linkedin_account_id"
  }'

# Review the response to understand lead overlap
# Look at duplicates_across_campaigns array
```

### Example 3: Data Consolidation

```bash
# Step 1: Import leads (may create cross-campaign duplicates)
curl -X POST /api/campaigns/{campaign_id}/leads/import-from-url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sales_navigator_url": "https://www.linkedin.com/sales/search/people?...",
    "account_id": "linkedin_account_id"
  }'

# Step 2: Merge duplicates to consolidate data
curl -X POST /api/campaigns/{campaign_id}/leads/merge-duplicates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "merge_strategy": "move"
  }'
```

## Best Practices

### 1. Pre-Import Planning
- **Check Duplicates First**: Use the check-duplicates endpoint before large imports
- **Review Cross-Campaign Data**: Understand lead overlap across campaigns
- **Plan Merge Strategy**: Decide whether to copy, move, or link duplicates

### 2. Import Strategy
- **Batch Imports**: Import leads in manageable batches
- **Monitor Responses**: Review duplication reports after each import
- **Track Metrics**: Use summary data for campaign performance analysis

### 3. Data Maintenance
- **Regular Cleanup**: Use merge-duplicates periodically to consolidate data
- **Archive Old Campaigns**: Consider archiving completed campaigns
- **Audit Cross-Campaign Duplicates**: Review overlap patterns for strategic insights

### 4. LinkedIn Compliance
- **Respect Rate Limits**: Avoid importing the same leads multiple times
- **Monitor Account Health**: Track connection request success rates
- **Follow Best Practices**: Maintain professional outreach standards

### 5. Performance Optimization
- **Use Pre-Check**: Avoid unnecessary API calls by checking duplicates first
- **Batch Operations**: Group duplicate operations when possible
- **Monitor Database Performance**: Large duplicate operations may impact performance

## Troubleshooting

### Common Issues

#### 1. Database Constraint Violations
**Error**: `IntegrityError: UNIQUE constraint failed`
**Cause**: Attempting to import duplicate within same campaign
**Solution**: Use check-duplicates endpoint before import

#### 2. High Cross-Campaign Duplicates
**Issue**: Many leads exist in multiple campaigns
**Analysis**: Review campaign targeting strategies
**Solution**: Consider consolidating campaigns or refining targeting

#### 3. Import Performance Issues
**Issue**: Slow import times with large datasets
**Cause**: Duplicate checking overhead
**Solution**: Use pre-check endpoint and import in smaller batches

#### 4. Merge Strategy Confusion
**Issue**: Unsure which merge strategy to use
**Guidance**:
- Use `copy` for multi-campaign outreach
- Use `move` for data consolidation
- Use `link` for relationship tracking (future)

### Debugging Tips

1. **Check Response Summaries**: Always review the summary section of import responses
2. **Monitor Logs**: Check server logs for detailed error information
3. **Test with Small Datasets**: Validate workflows with small lead lists first
4. **Verify Database State**: Check database directly for complex issues

### Support

For issues not covered in this guide:
1. Check the main API documentation
2. Review server logs for detailed error messages
3. Test with minimal data to isolate issues
4. Contact system administrator for database-level issues

## Conclusion

The duplication management system provides comprehensive protection against duplicate leads while offering flexibility for different business needs. By following the best practices outlined in this guide, you can maintain data quality, ensure LinkedIn compliance, and optimize your outreach campaigns.

Remember: The goal is not just to prevent duplicates, but to use duplication data as a strategic tool for better campaign management and business intelligence. 