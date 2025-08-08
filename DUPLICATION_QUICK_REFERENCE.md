# Duplication Management - Quick Reference

## 🎯 Overview
Prevent duplicate leads and manage data integrity across campaigns with our comprehensive duplication management system.

## 📋 API Endpoints

### 1. Advanced Search with Parameters
```bash
POST /api/campaigns/{campaign_id}/leads/search
```
**Purpose**: Perform advanced LinkedIn search using Sales Navigator parameters
**Use Case**: Build targeted searches with specific criteria

### 2. Search and Import with Duplication Management
```bash
POST /api/campaigns/{campaign_id}/leads/search-and-import
```
**Purpose**: One-step search and import with automatic duplication management
**Use Case**: Advanced lead sourcing with built-in duplicate prevention

### 3. Get Search Parameters
```bash
GET /api/search-parameters
```
**Purpose**: Get available search parameters (locations, industries, skills, etc.)
**Use Case**: Build advanced search queries with correct parameter IDs

### 4. Check Duplicates Before Import
```bash
POST /api/campaigns/{campaign_id}/leads/check-duplicates
```
**Purpose**: Pre-import duplicate detection
**Use Case**: Before importing large lead lists

### 5. Import with Duplication Reporting
```bash
POST /api/campaigns/{campaign_id}/leads/import-from-url
```
**Purpose**: Import leads with automatic duplicate detection
**Use Case**: Standard lead import with duplication awareness

### 6. Merge Duplicates
```bash
POST /api/campaigns/{campaign_id}/leads/merge-duplicates
```
**Purpose**: Consolidate duplicate leads across campaigns
**Use Case**: Data cleanup and consolidation

## 🔄 Duplication Types

### Campaign-Level Duplicates
- **Detection**: Same `public_identifier` within same campaign
- **Action**: Automatically skipped
- **Database**: Enforced by unique constraint

### Cross-Campaign Duplicates
- **Detection**: Same `public_identifier` across campaigns (same client)
- **Action**: Reported but imported
- **Use Case**: Understanding lead overlap

## 📊 Response Structure

```json
{
  "message": "Successfully imported 10 leads",
  "imported_leads": [...],
  "duplicates_skipped": [...],
  "duplicates_across_campaigns": [...],
  "summary": {
    "total_profiles_found": 15,
    "new_leads_imported": 10,
    "duplicates_in_campaign": 3,
    "duplicates_across_campaigns": 2,
    "errors": 0
  }
}
```

## 🎛️ Merge Strategies

| Strategy | Action | Use Case |
|----------|--------|----------|
| `copy` | Copy leads to target campaign | Multi-campaign outreach |
| `move` | Move data and delete duplicates | Data consolidation |
| `link` | Create references (future) | Relationship tracking |

## 🚀 Quick Workflows

### Safe Import Workflow
```bash
# 1. Check duplicates first
curl -X POST /api/campaigns/{id}/leads/check-duplicates \
  -d '{"public_identifiers": ["profile1", "profile2"]}'

# 2. Import with confidence
curl -X POST /api/campaigns/{id}/leads/import-from-url \
  -d '{"sales_navigator_url": "...", "account_id": "..."}'
```

### Data Consolidation Workflow
```bash
# 1. Import leads (may create duplicates)
curl -X POST /api/campaigns/{id}/leads/import-from-url \
  -d '{"sales_navigator_url": "...", "account_id": "..."}'

# 2. Merge duplicates
curl -X POST /api/campaigns/{id}/leads/merge-duplicates \
  -d '{"merge_strategy": "move"}'
```

## ⚡ Best Practices

### ✅ Do's
- Use `check-duplicates` before large imports
- Review `duplicates_across_campaigns` for insights
- Use `merge-duplicates` for data cleanup
- Monitor summary metrics

### ❌ Don'ts
- Import the same leads multiple times
- Ignore cross-campaign duplicate reports
- Skip pre-import duplicate checks
- Forget to monitor LinkedIn rate limits

## 🔧 Database Protection

```sql
-- Unique constraint prevents duplicates within campaigns
UNIQUE(campaign_id, public_identifier)
```

## 📈 Benefits

- **LinkedIn Compliance**: Avoid rate limit violations
- **Data Quality**: Accurate metrics and reporting
- **Efficiency**: Focus on unique prospects
- **Insights**: Understand campaign overlap
- **Automation**: Seamless duplicate handling

## 🆘 Common Issues

| Issue | Solution |
|-------|----------|
| `IntegrityError: UNIQUE constraint failed` | Use `check-duplicates` before import |
| High cross-campaign duplicates | Review campaign targeting strategies |
| Slow import performance | Use pre-check and smaller batches |
| Merge strategy confusion | Use `copy` for outreach, `move` for cleanup |

## 📚 Related Documentation

- [Comprehensive API Documentation](COMPREHENSIVE_API_DOCUMENTATION.md)
- [Duplication Management Guide](DUPLICATION_MANAGEMENT_GUIDE.md)
- [Main README](README.md)

---

**💡 Pro Tip**: Use the duplication data as a strategic tool for better campaign management and business intelligence! 