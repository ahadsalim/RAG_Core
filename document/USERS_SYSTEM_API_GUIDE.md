# Core API Integration Guide for Users System

## Overview

This guide provides complete documentation for integrating the Users System with Core RAG API.

**Base URL:** `https://core.tejarat.chat` (or `http://localhost:7001` for development)

**API Documentation:** `https://core.tejarat.chat/docs` (Swagger UI)

---

## Authentication

All API requests require JWT Bearer token in the Authorization header.

### JWT Configuration

**CRITICAL:** Users System must use the exact same JWT secret key as Core:

```env
JWT_SECRET_KEY="VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo"
JWT_ALGORITHM="HS256"
```

See `/srv/USERS_SYSTEM_JWT_GUIDE.md` for detailed JWT implementation guide.

### Creating JWT Token

```python
from jose import jwt
from datetime import datetime, timedelta

JWT_SECRET_KEY = "VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo"

def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,  # REQUIRED: Core expects user_id in 'sub' field
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")
```

### Using JWT in Requests

```bash
curl -X POST https://core.tejarat.chat/api/v1/query/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "سوال کاربر"}'
```

---

## Main Endpoints

### 1. Process Query (Main Endpoint)

Process user questions through RAG pipeline.

**Endpoint:** `POST /api/v1/query/`

**Authentication:** Required (JWT Bearer token)

**Request Body:**

```json
{
  "query": "قانون مدنی در مورد مالکیت چه می‌گوید؟",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",  // Optional
  "language": "fa",  // fa, en, or ar
  "max_results": 5,  // 1-20
  "filters": {  // Optional
    "jurisdiction": "جمهوری اسلامی ایران"
  },
  "use_cache": true,
  "use_reranking": true,
  "stream": false
}
```

**Response:**

```json
{
  "answer": "طبق ماده ۱۷۹ قانون مدنی، شکار کردن موجب تملک است...",
  "sources": ["dee1acff-8131-49ec-b7ed-78d543dcc539"],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_id": "660e8400-e29b-41d4-a716-446655440001",
  "tokens_used": 150,
  "processing_time_ms": 1200,
  "cached": false
}
```

**Rate Limits:**
- Free tier: 10 queries/day
- Basic tier: 50 queries/day
- Premium tier: 200 queries/day
- Enterprise tier: Unlimited

**Status Codes:**
- `200`: Success
- `401`: Invalid JWT token
- `429`: Daily limit exceeded
- `500`: Server error

---

### 2. Get User Profile

Retrieve user's profile information.

**Endpoint:** `GET /api/v1/users/profile`

**Authentication:** Required

**Response:**

```json
{
  "id": "user-123",
  "external_user_id": "user-123",
  "username": "user_abc",
  "email": "user@example.com",
  "full_name": "نام کاربر",
  "tier": "free",
  "daily_query_limit": 10,
  "daily_query_count": 3,
  "total_query_count": 150,
  "total_tokens_used": 5000,
  "language": "fa",
  "timezone": "Asia/Tehran",
  "last_active_at": "2025-11-17T06:00:00Z",
  "created_at": "2025-11-01T00:00:00Z"
}
```

---

### 3. Update User Profile

Update user preferences.

**Endpoint:** `PATCH /api/v1/users/profile`

**Authentication:** Required

**Request Body:**

```json
{
  "language": "fa",
  "timezone": "Asia/Tehran",
  "preferences": {
    "theme": "dark",
    "notifications": true
  }
}
```

**Response:**

```json
{
  "status": "success",
  "message": "Profile updated successfully"
}
```

---

### 4. Get Conversations

Retrieve user's conversation history.

**Endpoint:** `GET /api/v1/users/conversations`

**Authentication:** Required

**Query Parameters:**
- `limit`: Number of conversations (default: 20, max: 100)
- `offset`: Pagination offset (default: 0)

**Response:**

```json
{
  "conversations": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "سوالات قانون مدنی",
      "message_count": 5,
      "created_at": "2025-11-17T06:00:00Z",
      "updated_at": "2025-11-17T06:30:00Z"
    }
  ],
  "total": 10,
  "limit": 20,
  "offset": 0
}
```

---

### 5. Get Conversation Messages

Retrieve messages in a conversation.

**Endpoint:** `GET /api/v1/users/conversations/{conversation_id}/messages`

**Authentication:** Required

**Query Parameters:**
- `limit`: Number of messages (default: 50, max: 200)
- `offset`: Pagination offset (default: 0)

**Response:**

```json
{
  "messages": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "role": "user",
      "content": "قانون مدنی چیست؟",
      "created_at": "2025-11-17T06:00:00Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440002",
      "role": "assistant",
      "content": "قانون مدنی مجموعه قوانینی است که...",
      "sources": ["dee1acff-8131-49ec-b7ed-78d543dcc539"],
      "tokens_used": 150,
      "created_at": "2025-11-17T06:00:05Z"
    }
  ],
  "total": 10,
  "limit": 50,
  "offset": 0
}
```

---

### 6. Delete Conversation

Delete a conversation and all its messages.

**Endpoint:** `DELETE /api/v1/users/conversations/{conversation_id}`

**Authentication:** Required

**Response:**

```json
{
  "status": "success",
  "message": "Conversation deleted successfully"
}
```

---

### 7. Submit Feedback

Submit feedback for a message.

**Endpoint:** `POST /api/v1/query/feedback`

**Authentication:** Required

**Request Body:**

```json
{
  "message_id": "660e8400-e29b-41d4-a716-446655440002",
  "rating": 5,
  "feedback_type": "general",
  "feedback_text": "پاسخ عالی بود",
  "suggested_response": null
}
```

**Response:**

```json
{
  "status": "success",
  "message": "Feedback submitted successfully"
}
```

---

### 8. Get User Statistics

Get user usage statistics.

**Endpoint:** `GET /api/v1/users/statistics`

**Authentication:** Required

**Response:**

```json
{
  "total_queries": 150,
  "total_tokens": 5000,
  "total_conversations": 10,
  "total_feedback": 25,
  "account_tier": "free",
  "created_at": "2025-11-01T00:00:00Z",
  "last_active": "2025-11-17T06:00:00Z"
}
```

---

### 9. Clear User History

Clear all user conversations and messages.

**Endpoint:** `POST /api/v1/users/clear-history`

**Authentication:** Required

**Response:**

```json
{
  "status": "success",
  "message": "History cleared successfully",
  "deleted_conversations": 10,
  "deleted_messages": 50
}
```

---

## Streaming Responses

For real-time response display, use streaming mode.

**Endpoint:** `POST /api/v1/query/stream`

**Request:**

```json
{
  "query": "قانون مدنی چیست؟",
  "stream": true
}
```

**Response:** Server-Sent Events (SSE)

```
data: {"token": "قانون", "finish_reason": null}
data: {"token": " مدنی", "finish_reason": null}
data: {"token": " مجموعه", "finish_reason": null}
...
data: {"token": "", "finish_reason": "stop"}
```

**Client Example (JavaScript):**

```javascript
const eventSource = new EventSource('/api/v1/query/stream', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.finish_reason) {
    eventSource.close();
  } else {
    displayToken(data.token);
  }
};
```

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message",
  "type": "ErrorType",
  "path": "/api/v1/query/"
}
```

### Common Errors

| Status Code | Error | Description | Solution |
|-------------|-------|-------------|----------|
| 401 | Unauthorized | Invalid JWT token | Check JWT_SECRET_KEY matches Core |
| 403 | Forbidden | Access denied | User doesn't own this resource |
| 429 | Too Many Requests | Rate limit exceeded | Upgrade user tier or wait |
| 422 | Validation Error | Invalid request data | Check request format |
| 500 | Internal Server Error | Server error | Contact support |

---

## Best Practices

### 1. Token Management

```python
# Cache tokens (they're valid for 30 minutes)
class TokenManager:
    def __init__(self):
        self.tokens = {}
    
    def get_token(self, user_id: str) -> str:
        if user_id in self.tokens:
            # Check if token is still valid
            payload = jwt.decode(self.tokens[user_id], options={"verify_signature": False})
            if payload['exp'] > time.time():
                return self.tokens[user_id]
        
        # Create new token
        token = create_token(user_id)
        self.tokens[user_id] = token
        return token
```

### 2. Error Handling

```python
import requests

def query_core(user_id: str, query: str):
    token = create_token(user_id)
    
    try:
        response = requests.post(
            "https://core.tejarat.chat/api/v1/query/",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": query},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            # JWT error - check configuration
            raise Exception("JWT authentication failed")
        elif e.response.status_code == 429:
            # Rate limit - inform user
            raise Exception("Daily limit exceeded")
        else:
            raise
    
    except requests.exceptions.Timeout:
        raise Exception("Request timeout")
```

### 3. Conversation Management

```python
# Always include conversation_id for follow-up questions
def send_query(user_id: str, query: str, conversation_id: str = None):
    token = create_token(user_id)
    
    payload = {
        "query": query,
        "language": "fa",
        "use_cache": True
    }
    
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    response = requests.post(
        "https://core.tejarat.chat/api/v1/query/",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    
    data = response.json()
    
    # Save conversation_id for next query
    return {
        "answer": data["answer"],
        "conversation_id": data["conversation_id"],
        "sources": data["sources"]
    }
```

### 4. Rate Limit Handling

```python
def check_user_limits(user_id: str) -> dict:
    """Check user's remaining queries"""
    token = create_token(user_id)
    
    response = requests.get(
        "https://core.tejarat.chat/api/v1/users/profile",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    profile = response.json()
    
    return {
        "tier": profile["tier"],
        "limit": profile["daily_query_limit"],
        "used": profile["daily_query_count"],
        "remaining": profile["daily_query_limit"] - profile["daily_query_count"]
    }
```

---

## Testing

### 1. Test JWT Authentication

```bash
# Create test token
python3 << EOF
from jose import jwt
from datetime import datetime, timedelta

JWT_SECRET_KEY = "VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo"

payload = {
    "sub": "test-user-123",
    "exp": datetime.utcnow() + timedelta(minutes=30)
}

token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")
print(token)
EOF

# Test with token
TOKEN="<your_token>"
curl -X GET https://core.tejarat.chat/api/v1/users/profile \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Test Query Endpoint

```bash
curl -X POST https://core.tejarat.chat/api/v1/query/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "قانون مدنی چیست؟",
    "language": "fa",
    "max_results": 5
  }'
```

### 3. Test Conversation Flow

```bash
# First query (creates conversation)
RESPONSE=$(curl -s -X POST https://core.tejarat.chat/api/v1/query/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "قانون مدنی چیست؟"}')

# Extract conversation_id
CONV_ID=$(echo $RESPONSE | jq -r '.conversation_id')

# Follow-up query (same conversation)
curl -X POST https://core.tejarat.chat/api/v1/query/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"ماده ۱۷۹ آن چیست؟\",
    \"conversation_id\": \"$CONV_ID\"
  }"
```

---

## Swagger UI

Interactive API documentation is available at:

**URL:** `https://core.tejarat.chat/docs`

Features:
- ✅ Complete API reference
- ✅ Try out endpoints directly
- ✅ Request/response examples
- ✅ Schema definitions
- ✅ Authentication testing

---

## Support

For issues or questions:

1. **Check Swagger UI:** `https://core.tejarat.chat/docs`
2. **Check JWT Guide:** `/srv/USERS_SYSTEM_JWT_GUIDE.md`
3. **Check Logs:**
   ```bash
   docker logs core-api --tail 100 | grep -i "error\|jwt\|auth"
   ```
4. **Contact Core Team** with:
   - Error message
   - Request/response samples
   - JWT token (for debugging only)

---

## Summary

### Quick Start Checklist

- [ ] Set `JWT_SECRET_KEY` in Users System `.env`
- [ ] Verify JWT_SECRET_KEY matches Core
- [ ] Implement token creation function
- [ ] Test authentication with `/api/v1/users/profile`
- [ ] Test query with `/api/v1/query/`
- [ ] Implement error handling
- [ ] Test conversation flow
- [ ] Review Swagger UI documentation

### Key Points

1. **JWT_SECRET_KEY must be identical** in both systems
2. **User ID goes in `sub` field** of JWT payload
3. **All endpoints require JWT** except health check
4. **Rate limits apply** based on user tier
5. **Use conversation_id** for follow-up questions
6. **Check Swagger UI** for complete documentation
