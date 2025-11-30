# راهنمای فنی یکپارچه‌سازی زیرسیستم Users با Core System

**نسخه:** 2.0.0  
**تاریخ:** 2025-11-29

## نمای کلی
زیرسیستم Users مسئول مدیریت کاربران، احراز هویت، مدیریت اشتراک، پرداخت و رابط کاربری است. کاربران از طریق این زیرسیستم سوالات خود را مطرح کرده و پاسخ‌ها را دریافت می‌کنند.

## ✨ قابلیت‌های جدید نسخه 2.0

1. **تحلیل فایل با LLM** - فایل‌های ضمیمه قبل از پردازش تحلیل می‌شوند
2. **حافظه کوتاه‌مدت** - 10 پیام آخر در پاسخ‌دهی لحاظ می‌شود
3. **حافظه بلندمدت** - خلاصه مکالمات قبلی ذخیره و استفاده می‌شود
4. **پشتیبانی از فایل‌های ضمیمه** - تصویر، PDF، TXT با MinIO

## معماری ارتباطی

```
┌─────────────────┐     Query/Response    ┌─────────────────┐
│                 │ --------------------> │                 │
│  Users System   │                       │   Core System   │
│   (Frontend)    │ <-------------------- │   (Backend)     │
└─────────────────┘     JWT Auth          └─────────────────┘
```

## API Endpoints که Users System باید فراخوانی کند

### 1. پردازش سوال کاربر (Endpoint اصلی)

#### Endpoint: `POST /api/v1/query/`

**Headers:**
```json
{
  "Authorization": "Bearer {JWT_TOKEN}",
  "Content-Type": "application/json"
}
```

**Request Body:**
```json
{
  "query": "قانون مدنی در مورد مالکیت چه می‌گوید؟",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",  // اختیاری - برای حافظه مکالمات
  "language": "fa",
  "max_results": 5,
  "filters": {
    "jurisdiction": "جمهوری اسلامی ایران",
    "category": "قانون مدنی"
  },
  "use_cache": true,
  "use_reranking": true,
  "stream": false,
  "file_attachments": [  // جدید: فایل‌های ضمیمه
    {
      "filename": "contract.pdf",
      "minio_url": "temp_uploads/user123/uuid_contract.pdf",
      "file_type": "application/pdf",
      "size_bytes": 524288
    }
  ]
}
```

**Response (200 OK):**
```json
{
  "answer": "طبق ماده ۱۷۹ قانون مدنی، شکار کردن موجب تملک است. این بدان معناست که...",
  "sources": [
    "dee1acff-8131-49ec-b7ed-78d543dcc539",
    "abc123-456-789"
  ],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_id": "660e8400-e29b-41d4-a716-446655440001",
  "tokens_used": 150,
  "processing_time_ms": 1200,
  "file_analysis": "فایل ضمیمه یک قرارداد کار است...",  // جدید: تحلیل فایل
  "context_used": true  // جدید: آیا از حافظه استفاده شد
}
```

**Error Responses:**
- `401 Unauthorized`: JWT token نامعتبر یا منقضی شده
- `429 Too Many Requests`: محدودیت روزانه کاربر تمام شده
- `500 Internal Server Error`: خطای سرور

### 2. پردازش سوال با Streaming

#### Endpoint: `POST /api/v1/query/stream`

**Headers:**
```json
{
  "Authorization": "Bearer {JWT_TOKEN}",
  "Content-Type": "application/json"
}
```

**Request:** همانند endpoint عادی

**Response:** Server-Sent Events (SSE) stream
```
data: {"token": "طبق", "finish_reason": null}
data: {"token": "ماده", "finish_reason": null}
data: {"token": "۱۷۹", "finish_reason": null}
...
data: {"token": "", "finish_reason": "stop"}
```

### 3. ارسال بازخورد کاربر

#### Endpoint: `POST /api/v1/query/feedback`

**Headers:**
```json
{
  "Authorization": "Bearer {JWT_TOKEN}",
  "Content-Type": "application/json"
}
```

**Request Body:**
```json
{
  "message_id": "660e8400-e29b-41d4-a716-446655440001",
  "rating": 5,  // 1-5
  "feedback_type": "accuracy",  // accuracy, relevance, completeness, clarity
  "feedback_text": "پاسخ کامل و دقیق بود",
  "suggested_response": null  // پیشنهاد کاربر برای پاسخ بهتر
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Feedback received"
}
```

## User Management APIs

### 4. دریافت پروفایل کاربر

#### Endpoint: `GET /api/v1/users/profile`

**Headers:**
```json
{
  "Authorization": "Bearer {JWT_TOKEN}"
}
```

**Response:**
```json
{
  "id": "user-uuid",
  "external_user_id": "users-system-id",
  "username": "user123",
  "email": "user@example.com",
  "full_name": "نام کاربر",
  "tier": "premium",  // free, basic, premium, enterprise
  "daily_query_limit": 200,
  "daily_query_count": 45,
  "total_query_count": 1250,
  "language": "fa",
  "timezone": "Asia/Tehran",
  "last_active_at": "2025-11-17T06:00:00Z",
  "created_at": "2025-01-01T00:00:00Z"
}
```

### 5. بروزرسانی تنظیمات کاربر

#### Endpoint: `PATCH /api/v1/users/profile`

**Headers:**
```json
{
  "Authorization": "Bearer {JWT_TOKEN}",
  "Content-Type": "application/json"
}
```

**Request Body:**
```json
{
  "language": "en",
  "timezone": "UTC",
  "preferences": {
    "theme": "dark",
    "notification_enabled": true,
    "email_summary": "weekly"
  }
}
```

### 6. دریافت لیست مکالمات

#### Endpoint: `GET /api/v1/users/conversations`

**Headers:**
```json
{
  "Authorization": "Bearer {JWT_TOKEN}"
}
```

**Query Parameters:**
- `limit`: تعداد نتایج (پیش‌فرض: 20، حداکثر: 100)
- `offset`: شروع از (برای صفحه‌بندی)

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "سوال در مورد قانون مدنی",
    "summary": "بحث در مورد مواد مالکیت",
    "message_count": 10,
    "total_tokens": 1500,
    "last_message_at": "2025-11-17T05:30:00Z",
    "created_at": "2025-11-17T05:00:00Z"
  }
]
```

### 7. دریافت پیام‌های یک مکالمه

#### Endpoint: `GET /api/v1/users/conversations/{conversation_id}/messages`

**Headers:**
```json
{
  "Authorization": "Bearer {JWT_TOKEN}"
}
```

**Query Parameters:**
- `limit`: تعداد پیام‌ها (پیش‌فرض: 50)
- `offset`: شروع از

**Response:**
```json
[
  {
    "id": "message-uuid",
    "role": "user",  // user, assistant, system
    "content": "قانون مدنی در مورد مالکیت چه می‌گوید؟",
    "tokens": 15,
    "sources": null,
    "feedback_rating": null,
    "created_at": "2025-11-17T05:00:00Z"
  },
  {
    "id": "message-uuid-2",
    "role": "assistant",
    "content": "طبق قانون مدنی ایران...",
    "tokens": 150,
    "sources": ["doc-id-1", "doc-id-2"],
    "feedback_rating": 5,
    "created_at": "2025-11-17T05:00:15Z"
  }
]
```

### 8. ایجاد مکالمه جدید

#### Endpoint: `POST /api/v1/users/conversations`

**Headers:**
```json
{
  "Authorization": "Bearer {JWT_TOKEN}",
  "Content-Type": "application/json"
}
```

**Request Body:**
```json
{
  "title": "سوال در مورد قانون کار",
  "context": {
    "topic": "labor_law",
    "preferences": {
      "detail_level": "comprehensive"
    }
  },
  "llm_model": "gpt-4-turbo",  // اختیاری
  "temperature": 0.7,  // اختیاری
  "max_tokens": 4096  // اختیاری
}
```

### 9. حذف مکالمه

#### Endpoint: `DELETE /api/v1/users/conversations/{conversation_id}`

**Headers:**
```json
{
  "Authorization": "Bearer {JWT_TOKEN}"
}
```

## Authentication & Authorization

### JWT Token Structure

**Payload:**
```json
{
  "sub": "user-id",  // شناسه کاربر
  "username": "user123",
  "email": "user@example.com",
  "tier": "premium",
  "exp": 1700000000,  // زمان انقضا
  "iat": 1699900000,  // زمان صدور
  "type": "access"  // access یا refresh
}
```

### Token Management

#### ایجاد JWT Token (در Users System)
```python
import jwt
from datetime import datetime, timedelta

def create_jwt_token(user_data: dict) -> str:
    payload = {
        "sub": user_data["id"],
        "username": user_data["username"],
        "email": user_data["email"],
        "tier": user_data["tier"],
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    token = jwt.encode(
        payload,
        JWT_SECRET_KEY,  # باید با Core هماهنگ باشد
        algorithm="HS256"
    )
    
    return token
```

#### Refresh Token Flow
```python
# 1. ایجاد refresh token
refresh_payload = {
    "sub": user_id,
    "type": "refresh",
    "exp": datetime.utcnow() + timedelta(days=7)
}

# 2. استفاده از refresh token برای دریافت access token جدید
@app.post("/auth/refresh")
async def refresh_token(refresh_token: str):
    # اعتبارسنجی refresh token
    # صدور access token جدید
    pass
```

## User Tier Management

### سطوح کاربری و محدودیت‌ها

| Tier | Daily Queries | Max Tokens | Features |
|------|--------------|------------|----------|
| Free | 10 | 1000 | Basic search |
| Basic | 50 | 2000 | Cache access, History |
| Premium | 200 | 4000 | Priority support, Advanced filters |
| Enterprise | Unlimited | 8000 | API access, Custom models |

### بررسی محدودیت‌ها (قبل از ارسال query)
```python
async def check_user_limits(user_id: str) -> bool:
    # دریافت پروفایل کاربر از Core
    profile = await get_user_profile(user_id)
    
    if profile["tier"] == "enterprise":
        return True
    
    if profile["daily_query_count"] >= profile["daily_query_limit"]:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Daily limit exceeded",
                "limit": profile["daily_query_limit"],
                "used": profile["daily_query_count"],
                "reset_at": "00:00 UTC"
            }
        )
    
    return True
```

## Conversation Management

### ذخیره‌سازی محلی تاریخچه
```python
# Schema برای ذخیره محلی در Users System
class ConversationCache:
    user_id: str
    conversation_id: str
    messages: List[Dict]
    last_synced: datetime
    
    async def sync_with_core(self):
        """همگام‌سازی با Core"""
        pass
```

### Real-time Updates
```javascript
// استفاده از WebSocket برای آپدیت‌های real-time
const ws = new WebSocket('wss://core.domain.com/ws');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'token') {
        // نمایش توکن جدید
        appendToResponse(data.token);
    } else if (data.type === 'complete') {
        // پایان پاسخ
        finalizeResponse(data);
    }
};
```

## Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "شما به حد مجاز درخواست‌های روزانه رسیده‌اید",
    "details": {
      "limit": 50,
      "used": 50,
      "reset_time": "2025-11-18T00:00:00Z"
    }
  }
}
```

### Error Codes

| Code | Description | Action |
|------|-------------|--------|
| AUTH_INVALID | Token نامعتبر | درخواست token جدید |
| AUTH_EXPIRED | Token منقضی شده | استفاده از refresh token |
| RATE_LIMIT_EXCEEDED | محدودیت rate | انتظار یا ارتقا tier |
| QUOTA_EXCEEDED | محدودیت روزانه | انتظار تا reset |
| INVALID_REQUEST | درخواست نامعتبر | اصلاح پارامترها |
| SERVER_ERROR | خطای سرور | retry با backoff |

## Implementation Examples

### 1. Query Client Implementation
```python
import httpx
import asyncio
from typing import Optional, Dict, Any

class CoreQueryClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def process_query(
        self,
        query: str,
        jwt_token: str,
        conversation_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """ارسال query به Core"""
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "conversation_id": conversation_id,
            "language": kwargs.get("language", "fa"),
            "max_results": kwargs.get("max_results", 5),
            "use_cache": kwargs.get("use_cache", True),
            "use_reranking": kwargs.get("use_reranking", True)
        }
        
        # اضافه کردن فیلترها اگر وجود دارد
        if "filters" in kwargs:
            payload["filters"] = kwargs["filters"]
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/query/",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Handle rate limit
                raise RateLimitError("Daily limit exceeded")
            elif e.response.status_code == 401:
                # Handle auth error
                raise AuthError("Invalid or expired token")
            else:
                raise
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

# استفاده
async def main():
    client = CoreQueryClient("https://core.domain.com")
    
    result = await client.process_query(
        query="قانون مدنی در مورد ارث چیست؟",
        jwt_token="eyJ0eXAiOiJKV1QiLCJhbGc...",
        filters={
            "category": "قانون مدنی",
            "jurisdiction": "ایران"
        }
    )
    
    print(f"Answer: {result['answer']}")
    print(f"Sources: {result['sources']}")
```

### 2. Streaming Response Handler
```javascript
// JavaScript/React implementation
class StreamingQueryHandler {
    constructor(coreUrl, jwtToken) {
        this.coreUrl = coreUrl;
        this.jwtToken = jwtToken;
    }
    
    async streamQuery(query, onToken, onComplete, onError) {
        const response = await fetch(`${this.coreUrl}/api/v1/query/stream`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.jwtToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                stream: true,
                language: 'fa'
            })
        });
        
        if (!response.ok) {
            onError(await response.json());
            return;
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));
                    
                    if (data.finish_reason === 'stop') {
                        onComplete(data);
                    } else if (data.token) {
                        onToken(data.token);
                    }
                }
            }
        }
    }
}

// استفاده در React Component
const QueryComponent = () => {
    const [response, setResponse] = useState('');
    const [loading, setLoading] = useState(false);
    
    const handleQuery = async (query) => {
        setLoading(true);
        setResponse('');
        
        const handler = new StreamingQueryHandler(
            process.env.REACT_APP_CORE_URL,
            localStorage.getItem('jwt_token')
        );
        
        await handler.streamQuery(
            query,
            (token) => setResponse(prev => prev + token),
            (data) => setLoading(false),
            (error) => {
                console.error(error);
                setLoading(false);
            }
        );
    };
    
    return (
        <div>
            <input onSubmit={(e) => handleQuery(e.target.value)} />
            <div>{response}</div>
            {loading && <LoadingSpinner />}
        </div>
    );
};
```

### 3. Conversation Manager
```python
class ConversationManager:
    def __init__(self, core_client: CoreQueryClient):
        self.core_client = core_client
        self.conversations = {}  # Local cache
    
    async def create_conversation(
        self, 
        user_id: str,
        title: str = None
    ) -> str:
        """ایجاد مکالمه جدید"""
        conv_id = str(uuid.uuid4())
        self.conversations[conv_id] = {
            "id": conv_id,
            "user_id": user_id,
            "title": title,
            "messages": [],
            "created_at": datetime.utcnow()
        }
        return conv_id
    
    async def add_message(
        self,
        conversation_id: str,
        query: str,
        jwt_token: str
    ):
        """افزودن پیام و دریافت پاسخ"""
        # ارسال به Core
        response = await self.core_client.process_query(
            query=query,
            jwt_token=jwt_token,
            conversation_id=conversation_id
        )
        
        # ذخیره محلی
        if conversation_id in self.conversations:
            self.conversations[conversation_id]["messages"].extend([
                {
                    "role": "user",
                    "content": query,
                    "timestamp": datetime.utcnow()
                },
                {
                    "role": "assistant",
                    "content": response["answer"],
                    "sources": response["sources"],
                    "timestamp": datetime.utcnow()
                }
            ])
        
        return response
```

## Performance Optimization

### 1. Caching Strategy
```python
# استفاده از Redis برای cache کردن نتایج
import redis
import hashlib
import json

class QueryCache:
    def __init__(self):
        self.redis = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
    
    def get_cache_key(self, query: str, filters: dict = None) -> str:
        """تولید کلید cache"""
        cache_data = f"{query}:{json.dumps(filters or {})}"
        return f"query:{hashlib.md5(cache_data.encode()).hexdigest()}"
    
    async def get(self, query: str, filters: dict = None) -> Optional[dict]:
        """دریافت از cache"""
        key = self.get_cache_key(query, filters)
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set(
        self, 
        query: str,
        result: dict,
        filters: dict = None,
        ttl: int = 3600
    ):
        """ذخیره در cache"""
        key = self.get_cache_key(query, filters)
        self.redis.setex(
            key,
            ttl,
            json.dumps(result)
        )
```

### 2. Request Batching
```python
# گروه‌بندی درخواست‌های مشابه
class RequestBatcher:
    def __init__(self, batch_window: float = 0.1):
        self.batch_window = batch_window
        self.pending_requests = []
        self.lock = asyncio.Lock()
    
    async def add_request(self, query: str, callback):
        """افزودن درخواست به batch"""
        async with self.lock:
            self.pending_requests.append({
                "query": query,
                "callback": callback
            })
            
            # اگر این اولین درخواست است، شروع timer
            if len(self.pending_requests) == 1:
                asyncio.create_task(self._process_batch())
    
    async def _process_batch(self):
        """پردازش batch"""
        await asyncio.sleep(self.batch_window)
        
        async with self.lock:
            requests = self.pending_requests
            self.pending_requests = []
        
        # ارسال همه درخواست‌ها به Core
        results = await self._send_batch(requests)
        
        # فراخوانی callbacks
        for req, result in zip(requests, results):
            req["callback"](result)
```

## Monitoring & Analytics

### 1. Usage Metrics
```python
# متریک‌های استفاده
METRICS = {
    "queries_total": Counter("queries_total", ["user_tier", "status"]),
    "query_duration": Histogram("query_duration_seconds"),
    "tokens_used": Counter("tokens_used_total", ["user_tier"]),
    "cache_hits": Counter("cache_hits_total"),
    "error_rate": Counter("errors_total", ["error_type"])
}

# ثبت متریک
async def track_query(user_tier: str, duration: float, tokens: int):
    METRICS["queries_total"].labels(user_tier, "success").inc()
    METRICS["query_duration"].observe(duration)
    METRICS["tokens_used"].labels(user_tier).inc(tokens)
```

### 2. User Analytics
```python
# تحلیل رفتار کاربران
class UserAnalytics:
    async def track_event(
        self,
        user_id: str,
        event_type: str,
        properties: dict
    ):
        """ثبت رویداد کاربر"""
        event = {
            "user_id": user_id,
            "event_type": event_type,
            "properties": properties,
            "timestamp": datetime.utcnow()
        }
        
        # ارسال به سیستم analytics
        await self.send_to_analytics(event)
    
    async def get_user_insights(self, user_id: str) -> dict:
        """دریافت insights کاربر"""
        return {
            "most_queried_topics": [...],
            "average_query_length": 45,
            "preferred_language": "fa",
            "peak_usage_hours": [14, 15, 16],
            "satisfaction_score": 4.5
        }
```

## Security Considerations

### 1. Input Validation
```python
from pydantic import BaseModel, validator

class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    language: str = "fa"
    
    @validator('query')
    def validate_query(cls, v):
        # حذف کاراکترهای مضر
        v = v.strip()
        
        # بررسی طول
        if len(v) < 3:
            raise ValueError("Query too short")
        if len(v) > 2000:
            raise ValueError("Query too long")
        
        # بررسی محتوای نامناسب
        # ...
        
        return v
    
    @validator('language')
    def validate_language(cls, v):
        allowed = ["fa", "en", "ar"]
        if v not in allowed:
            raise ValueError(f"Language must be one of {allowed}")
        return v
```

### 2. Rate Limiting
```python
# پیاده‌سازی rate limiting
from aioredis import Redis
import time

class RateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def check_rate_limit(
        self,
        user_id: str,
        limit: int = 60,
        window: int = 60
    ) -> bool:
        """بررسی rate limit"""
        key = f"rate:{user_id}"
        current_time = int(time.time())
        window_start = current_time - window
        
        # حذف درخواست‌های قدیمی
        await self.redis.zremrangebyscore(key, 0, window_start)
        
        # شمارش درخواست‌های فعلی
        count = await self.redis.zcard(key)
        
        if count >= limit:
            return False
        
        # افزودن درخواست جدید
        await self.redis.zadd(key, {str(current_time): current_time})
        await self.redis.expire(key, window)
        
        return True
```