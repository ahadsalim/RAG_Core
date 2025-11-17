# Ingest API Requirements for Core System

## Overview
Core system needs to sync embeddings from Ingest system. Currently, Core connects directly to Ingest database which violates separation of concerns. This document specifies the required APIs that Ingest should provide.

## Architecture

**Recommended: Push-based (Webhook)**
```
Ingest System → POST /api/v1/sync/embeddings → Core API
```

**Alternative: Pull-based (Polling)**
```
Core System → GET /api/v1/embeddings/changes → Ingest API
```

---

## Option 1: Webhook (Recommended) ✅

### Ingest Configuration
Ingest should send webhooks to Core when:
- New embedding is created
- Embedding is updated
- Document is deleted

**Webhook URL:** `https://core.domain.com/api/v1/sync/embeddings`
**Method:** POST
**Authentication:** `X-API-Key: {INGEST_API_KEY}`

**Payload:**
```json
{
  "embeddings": [
    {
      "id": "uuid-string",
      "vector": [0.1, 0.2, 0.3, ...],
      "text": "متن اصلی سند",
      "document_id": "uuid-string",
      "metadata": {
        "chunk_id": "uuid",
        "unit_id": "uuid",
        "work_id": "uuid",
        "work_title": "قانون مدنی",
        "unit_type": "article",
        "unit_number": "179",
        "language": "fa",
        "jurisdiction": "جمهوری اسلامی ایران",
        "authority": "مجلس شورای اسلامی",
        "valid_from": "1935-10-31",
        "is_active": true,
        "token_count": 8
      }
    }
  ],
  "sync_type": "incremental"
}
```

**Response:**
```json
{
  "status": "success",
  "synced_count": 1,
  "timestamp": "2025-11-16T05:30:00Z"
}
```

---

## Option 2: Pull API (If webhook not possible)

### Required Endpoints in Ingest

#### 1. Get Changed Embeddings

**Endpoint:** `GET /api/v1/embeddings/changes`

**Headers:**
```
Authorization: Bearer {CORE_API_KEY}
```

**Query Parameters:**
- `since` (optional): ISO 8601 datetime - Only return changes after this time
- `limit` (optional): int (default: 100, max: 1000)
- `offset` (optional): int (default: 0)

**Response:**
```json
{
  "embeddings": [
    {
      "id": "uuid-string",
      "vector": [0.1, 0.2, ...],
      "dimension": 768,
      "text_content": "متن اصلی",
      "document_id": "uuid-string",
      "chunk_index": 0,
      "metadata": {
        "chunk_id": "uuid",
        "unit_id": "uuid",
        "work_id": "uuid",
        "expression_id": "uuid",
        "manifestation_id": "uuid",
        "work_title": "قانون مدنی",
        "unit_type": "article",
        "unit_number": "179",
        "path_label": "فصل 2 > قسمت 6 > ماده 179",
        "urn_lex": "",
        "consolidation_level": "base",
        "expression_date": "1935-10-31",
        "publication_date": "1935-10-31",
        "official_gazette": "روزنامه رسمی",
        "gazette_issue_no": "0",
        "source_url": "",
        "jurisdiction": "جمهوری اسلامی ایران",
        "authority": "مجلس شورای اسلامی",
        "valid_from": "1935-10-31",
        "valid_to": null,
        "is_active": true,
        "in_force_from": "1935-10-31",
        "in_force_to": null,
        "repeal_status": "in_force",
        "token_count": 8,
        "overlap_prev": 0,
        "overlap_next": 0,
        "language": "fa"
      },
      "created_at": "2025-11-14T21:05:27Z",
      "updated_at": "2025-11-14T21:05:27Z"
    }
  ],
  "pagination": {
    "total": 3347,
    "limit": 100,
    "offset": 0,
    "has_more": true
  },
  "sync_metadata": {
    "server_time": "2025-11-16T05:30:00Z",
    "oldest_change": "2025-11-14T20:00:00Z",
    "newest_change": "2025-11-16T05:29:55Z"
  }
}
```

**Status Codes:**
- 200: Success
- 401: Invalid API key
- 429: Rate limit exceeded
- 500: Server error

---

#### 2. Get Deleted Documents

**Endpoint:** `GET /api/v1/embeddings/deleted`

**Headers:**
```
Authorization: Bearer {CORE_API_KEY}
```

**Query Parameters:**
- `since` (optional): ISO 8601 datetime
- `limit` (optional): int (default: 100, max: 1000)

**Response:**
```json
{
  "deleted_documents": [
    {
      "document_id": "uuid-string",
      "deleted_at": "2025-11-16T05:00:00Z",
      "reason": "document_removed",
      "metadata": {
        "work_id": "uuid",
        "work_title": "قانون مدنی"
      }
    }
  ],
  "pagination": {
    "total": 5,
    "limit": 100,
    "has_more": false
  }
}
```

**Deletion Reasons:**
- `document_removed`: Document was explicitly deleted
- `unit_deleted`: Legal unit was deleted
- `work_archived`: Entire work was archived
- `superseded`: Document was replaced by newer version

---

#### 3. Get Sync Status

**Endpoint:** `GET /api/v1/embeddings/sync-status`

**Headers:**
```
Authorization: Bearer {CORE_API_KEY}
```

**Response:**
```json
{
  "total_embeddings": 3347,
  "last_updated": "2025-11-16T05:29:55Z",
  "pending_changes": 0,
  "models": {
    "intfloat/multilingual-e5-base": {
      "dimension": 768,
      "count": 3347,
      "last_generated": "2025-11-16T05:29:55Z"
    }
  },
  "health": {
    "status": "healthy",
    "database": "connected",
    "embedding_service": "running"
  }
}
```

---

## Authentication

All API calls from Core to Ingest should use:
```
Authorization: Bearer {CORE_API_KEY}
```

Or:
```
X-API-Key: {CORE_API_KEY}
```

This key should be:
- Generated by Ingest system
- Stored in Core's `.env` as `INGEST_API_KEY`
- Different from the key used by Ingest to call Core

---

## Rate Limiting

Recommended limits:
- `/embeddings/changes`: 60 requests/minute
- `/embeddings/deleted`: 60 requests/minute
- `/embeddings/sync-status`: 120 requests/minute

---

## Error Handling

All endpoints should return consistent error format:
```json
{
  "error": {
    "code": "INVALID_API_KEY",
    "message": "The provided API key is invalid or expired",
    "timestamp": "2025-11-16T05:30:00Z"
  }
}
```

**Error Codes:**
- `INVALID_API_KEY`: Authentication failed
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `INVALID_PARAMETERS`: Invalid query parameters
- `SERVER_ERROR`: Internal server error

---

## Implementation Priority

### Phase 1: Webhook (Recommended)
1. Ingest sends embeddings to Core via webhook
2. Core stores in Qdrant
3. No polling needed

### Phase 2: Pull API (Fallback)
1. Core polls Ingest for changes
2. Useful for:
   - Initial full sync
   - Recovery from webhook failures
   - Manual sync operations

---

## Testing

### Test Webhook
```bash
curl -X POST https://core.domain.com/api/v1/sync/embeddings \
  -H "X-API-Key: your-ingest-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "embeddings": [{
      "id": "test-123",
      "vector": [0.1, 0.2, 0.3],
      "text": "تست",
      "document_id": "doc-123",
      "metadata": {"language": "fa"}
    }],
    "sync_type": "incremental"
  }'
```

### Test Pull API
```bash
curl -X GET "https://ingest.domain.com/api/v1/embeddings/changes?limit=10" \
  -H "Authorization: Bearer your-core-api-key"
```

---

## Migration Plan

1. **Remove Direct DB Access:**
   - Remove `INGEST_DATABASE_URL` from Core
   - Remove `get_ingest_session()` usage
   - Remove SQL queries to Ingest DB

2. **Implement API Client:**
   - Create `IngestAPIClient` class in Core
   - Use `httpx` for async HTTP calls
   - Handle retries and errors

3. **Update Sync Service:**
   - Replace DB queries with API calls
   - Keep same interface for Core endpoints
   - Add proper error handling

4. **Configure Webhook:**
   - Add webhook URL in Ingest config
   - Test with sample data
   - Monitor webhook delivery

5. **Remove DB Credentials:**
   - Remove `ingest_reader` user (if exists)
   - Update documentation
   - Clean up `.env` files

---

## Questions for Ingest Team

1. **Webhook Support:**
   - Can Ingest send webhooks when embeddings change?
   - What retry mechanism does Ingest have for failed webhooks?

2. **API Availability:**
   - Is there an existing API for embeddings?
   - What authentication method is preferred?

3. **Rate Limits:**
   - What rate limits should Core expect?
   - Is there a bulk API for initial sync?

4. **Metadata:**
   - Is the metadata structure in this document correct?
   - Are there additional fields Core should store?

5. **Deletion:**
   - How does Ingest handle document deletion?
   - Should Core receive deletion events or poll for them?
