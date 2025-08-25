# Chat Archival System Documentation

## Overview

The Chat Archival System is an automated solution that manages chat lifecycle based on company retention policies. It automatically archives old chats and permanently deletes archived chats after a specified period.

## Features

- **Automated Chat Archival**: Archives chats based on company-specific retention settings
- **Automatic Deletion**: Permanently deletes archived chats after 3 months
- **Daily Scheduling**: Runs automatically every day at 23:00
- **Company-Specific Policies**: Each company can configure their own retention period
- **Monitoring & Management**: REST API endpoints for monitoring and manual control
- **Comprehensive Logging**: Detailed logging for audit and troubleshooting

## System Architecture

### Components

1. **ChatArchivalService** (`backend/beyond_the_loop/services/chat_archival_service.py`)
   - Core service handling archival and deletion logic
   - Company-specific retention policy enforcement
   - Statistics and preview functionality

2. **TaskScheduler** (`backend/beyond_the_loop/services/scheduler.py`)
   - Background scheduler using APScheduler
   - Daily execution at 23:00
   - Graceful startup and shutdown

3. **Chat Archival API** (`backend/beyond_the_loop/routers/chat_archival.py`)
   - REST endpoints for monitoring and management
   - Statistics, previews, and manual triggers
   - Admin and user access controls

## Configuration

### Company Retention Settings

Each company can configure their chat retention period through the company config:

```json
{
  "data": {
    "chat_retention_days": 30
  }
}
```

**Available retention periods:**
- 30 days (default)
- 90 days
- 180 days
- 270 days
- 365 days

### Deletion Policy

- **Archived chats** are permanently deleted after **90 days** (3 months)
- This deletion period is fixed and not configurable per company

## API Endpoints

All endpoints are prefixed with `/api/v1/chat-archival`

### User Endpoints

#### GET `/stats`
Get archival statistics for the user's company.

**Response:**
```json
{
  "total_chats": 150,
  "archived_chats": 45,
  "active_chats": 105,
  "archival_rate": 30.0
}
```

### Admin Endpoints

#### GET `/preview`
Preview which chats would be archived for the company.

**Response:**
```json
{
  "company_id": "company-uuid",
  "retention_days": 30,
  "cutoff_date": "2024-07-25T10:00:00",
  "candidates_count": 12,
  "candidates": [
    {
      "chat_id": "chat-uuid",
      "title": "Old Chat Title",
      "user_id": "user-uuid",
      "created_at": "2024-06-15T14:30:00",
      "days_old": 41
    }
  ]
}
```

#### GET `/scheduler/status`
Get current scheduler status and job information.

**Response:**
```json
{
  "running": true,
  "jobs": [
    {
      "id": "daily_chat_archival",
      "name": "Daily Chat Archival Process",
      "trigger": "cron[hour=23,minute=0]",
      "next_run": "2024-08-25T23:00:00+02:00"
    }
  ]
}
```

#### POST `/trigger`
Manually trigger the archival process (for testing/admin purposes).

**Response:**
```json
{
  "success": true,
  "start_time": "2024-08-25T10:00:00",
  "end_time": "2024-08-25T10:02:15",
  "duration_seconds": 135.5,
  "companies_processed": 5,
  "chats_archived": 23,
  "chats_deleted": 7
}
```

#### GET `/global-stats`
Get global archival statistics across all companies (admin only).

## Process Flow

### Daily Archival Process

1. **Startup** (23:00 daily)
   - Scheduler triggers the archival process
   - Service initializes counters and logs start

2. **Chat Archival Phase**
   - Query all companies with users who have chats
   - For each company:
     - Get company's `chat_retention_days` setting
     - Calculate cutoff date (current date - retention days)
     - Find non-archived chats older than cutoff date
     - Mark these chats as `archived = true`
     - Update `updated_at` timestamp

3. **Chat Deletion Phase**
   - Find all archived chats older than 90 days
   - Permanently delete these chats using existing `Chats.delete_chat_by_id()`
   - This also handles deletion of shared chats

4. **Completion**
   - Log summary statistics
   - Return process results

### Error Handling

- Company-level errors don't stop processing of other companies
- Individual chat deletion errors are logged but don't halt the process
- Failed companies are tracked and reported
- Comprehensive error logging for debugging

## Database Schema

### Chat Table Changes

The existing `chat` table uses the `archived` boolean field:

```sql
-- Existing field used by the archival system
archived BOOLEAN DEFAULT FALSE
```

### Company Config

Chat retention is stored in the company's JSON config:

```sql
-- In the config table
data JSON -- Contains: {"data": {"chat_retention_days": 30}}
```

## Monitoring & Logging

### Log Levels

- **INFO**: Normal operation, process start/completion, statistics
- **WARNING**: Non-critical issues, missing configurations
- **ERROR**: Process failures, individual operation errors

### Log Examples

```
INFO: Starting daily chat archival process
INFO: Processing company abc-123 with 15 users, retention: 30 days
INFO: Archived 8 chats for company abc-123
INFO: Deleted 3 old archived chats
INFO: Daily archival process completed successfully: {"chats_archived": 23, "chats_deleted": 7, "companies_processed": 5}
```

## Testing

### Test Script

Run the comprehensive test script:

```bash
cd backend
python test_chat_archival.py
```

The test script:
- Creates test company with 7-day retention policy
- Creates test chats of different ages
- Runs the archival process
- Verifies correct archival and deletion behavior
- Cleans up test data

### Manual Testing

1. **Preview Archival Candidates:**
   ```bash
   curl -X GET "http://localhost:8080/api/v1/chat-archival/preview" \
        -H "Authorization: Bearer <admin-token>"
   ```

2. **Trigger Manual Archival:**
   ```bash
   curl -X POST "http://localhost:8080/api/v1/chat-archival/trigger" \
        -H "Authorization: Bearer <admin-token>"
   ```

3. **Check Statistics:**
   ```bash
   curl -X GET "http://localhost:8080/api/v1/chat-archival/stats" \
        -H "Authorization: Bearer <user-token>"
   ```

## Deployment Considerations

### Scheduler Startup

The scheduler automatically starts when the FastAPI application starts and shuts down gracefully when the application stops.

### Timezone Configuration

The scheduler is configured for `Europe/Berlin` timezone. Adjust in `scheduler.py` if needed:

```python
self.scheduler = BackgroundScheduler(
    timezone='Your/Timezone'  # Change this
)
```

### Performance Considerations

- **Batch Processing**: The system processes chats in batches per company
- **Database Connections**: Uses connection pooling from the existing database setup
- **Memory Usage**: Minimal memory footprint, processes companies sequentially
- **Execution Time**: Typical execution takes 1-5 minutes depending on data volume

### Monitoring in Production

1. **Check Scheduler Status:**
   - Use the `/scheduler/status` endpoint
   - Monitor application logs for scheduler startup/shutdown

2. **Monitor Process Execution:**
   - Check daily logs around 23:00
   - Monitor the `/trigger` endpoint response for manual verification

3. **Database Monitoring:**
   - Monitor `archived` field distribution in chat table
   - Track chat deletion rates over time

## Troubleshooting

### Common Issues

1. **Scheduler Not Starting:**
   - Check application logs for scheduler startup errors
   - Verify APScheduler dependency is installed
   - Check timezone configuration

2. **No Chats Being Archived:**
   - Verify company has `chat_retention_days` configured
   - Check if chats are older than retention period
   - Verify users belong to companies

3. **Archival Process Failing:**
   - Check database connectivity
   - Verify user-company relationships
   - Review error logs for specific failures

### Debug Commands

```python
# Check company config
from beyond_the_loop.config import get_config_value
retention = get_config_value("data.chat_retention_days", "company-id")

# Preview archival candidates
from beyond_the_loop.services.chat_archival_service import chat_archival_service
preview = chat_archival_service.preview_archival_candidates("company-id")

# Get archival statistics
stats = chat_archival_service.get_archival_stats("company-id")
```

## Security Considerations

- **Admin Access**: Archival management endpoints require admin privileges
- **Company Isolation**: Each company's chats are processed independently
- **Data Deletion**: Permanent deletion is irreversible - ensure proper backups
- **Audit Trail**: All operations are logged for audit purposes

## Future Enhancements

Potential improvements for future versions:

1. **Configurable Deletion Period**: Allow companies to set custom deletion periods
2. **Backup Before Deletion**: Optional backup to external storage before deletion
3. **Selective Archival**: Archive based on chat activity, not just age
4. **Notification System**: Email notifications for archival activities
5. **Recovery Options**: Temporary recovery period before permanent deletion
