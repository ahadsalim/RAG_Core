# راهنمای سیستم Users برای ارتباط با Core

## معماری کلی

سیستم Users مسئول:
- مدیریت کاربران و احراز هویت
- رابط کاربری (UI)
- مدیریت پرداخت‌ها و اشتراک
- ارسال درخواست‌ها به Core

## API Endpoints سیستم Core

### 1. احراز هویت (Authentication)

سیستم Users باید برای هر کاربر یک JWT token از Core دریافت کند:

```typescript
// TypeScript example for Users system

interface AuthRequest {
  external_user_id: string;
  username: string;
  email?: string;
  tier: 'free' | 'basic' | 'premium' | 'enterprise';
}

async function authenticateWithCore(user: AuthRequest): Promise<string> {
  const response = await fetch(`${CORE_API_URL}/auth/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': USERS_API_KEY
    },
    body: JSON.stringify(user)
  });
  
  const data = await response.json();
  return data.access_token;
}
```

### 2. پردازش Query

```typescript
interface QueryRequest {
  query: string;
  conversation_id?: string;
  language?: 'fa' | 'en' | 'ar';
  max_results?: number;
  filters?: Record<string, any>;
  use_cache?: boolean;
  use_reranking?: boolean;
  stream?: boolean;
}

interface QueryResponse {
  answer: string;
  sources: string[];
  conversation_id: string;
  message_id: string;
  tokens_used: number;
  processing_time_ms: number;
  cached: boolean;
}

async function sendQuery(
  query: QueryRequest, 
  userToken: string
): Promise<QueryResponse> {
  const response = await fetch(`${CORE_API_URL}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userToken}`
    },
    body: JSON.stringify(query)
  });
  
  if (!response.ok) {
    throw new Error(`Query failed: ${response.statusText}`);
  }
  
  return response.json();
}
```

### 3. Streaming Response

برای دریافت پاسخ به صورت stream:

```typescript
async function* streamQuery(
  query: QueryRequest,
  userToken: string
): AsyncGenerator<string> {
  const response = await fetch(`${CORE_API_URL}/query/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userToken}`
    },
    body: JSON.stringify({ ...query, stream: true })
  });
  
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  
  if (!reader) throw new Error('No response body');
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.trim()) {
        const data = JSON.parse(line);
        yield data.token;
      }
    }
  }
}
```

### 4. ارسال Feedback

```typescript
interface FeedbackRequest {
  message_id: string;
  rating: 1 | 2 | 3 | 4 | 5;
  feedback_type?: string;
  feedback_text?: string;
  suggested_response?: string;
}

async function submitFeedback(
  feedback: FeedbackRequest,
  userToken: string
): Promise<void> {
  const response = await fetch(`${CORE_API_URL}/query/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userToken}`
    },
    body: JSON.stringify(feedback)
  });
  
  if (!response.ok) {
    throw new Error(`Feedback submission failed`);
  }
}
```

### 5. مدیریت مکالمات

```typescript
// Get user conversations
async function getUserConversations(userToken: string) {
  const response = await fetch(`${CORE_API_URL}/users/conversations`, {
    headers: {
      'Authorization': `Bearer ${userToken}`
    }
  });
  
  return response.json();
}

// Get conversation history
async function getConversationHistory(
  conversationId: string,
  userToken: string
) {
  const response = await fetch(
    `${CORE_API_URL}/users/conversations/${conversationId}/messages`,
    {
      headers: {
        'Authorization': `Bearer ${userToken}`
      }
    }
  );
  
  return response.json();
}

// Delete conversation
async function deleteConversation(
  conversationId: string,
  userToken: string
) {
  const response = await fetch(
    `${CORE_API_URL}/users/conversations/${conversationId}`,
    {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${userToken}`
      }
    }
  );
  
  return response.ok;
}
```

## مدیریت صوت و تصویر

### 1. جستجوی صوتی

```typescript
async function voiceSearch(
  audioBlob: Blob,
  userToken: string
): Promise<QueryResponse> {
  const formData = new FormData();
  formData.append('audio', audioBlob);
  formData.append('language', 'fa');
  
  const response = await fetch(`${CORE_API_URL}/query/voice`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${userToken}`
    },
    body: formData
  });
  
  return response.json();
}
```

### 2. جستجوی تصویری (OCR)

```typescript
async function imageSearch(
  imageFile: File,
  userToken: string
): Promise<QueryResponse> {
  const formData = new FormData();
  formData.append('image', imageFile);
  
  const response = await fetch(`${CORE_API_URL}/query/image`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${userToken}`
    },
    body: formData
  });
  
  return response.json();
}
```

## WebSocket برای Real-time

```typescript
class CoreWebSocket {
  private ws: WebSocket;
  private userToken: string;
  
  constructor(userToken: string) {
    this.userToken = userToken;
    this.ws = new WebSocket(`ws://localhost:7001/ws?token=${userToken}`);
    
    this.ws.onopen = () => {
      console.log('Connected to Core');
    };
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };
  }
  
  sendQuery(query: string) {
    this.ws.send(JSON.stringify({
      type: 'query',
      data: { query }
    }));
  }
  
  private handleMessage(data: any) {
    switch(data.type) {
      case 'token':
        // Handle streaming token
        break;
      case 'complete':
        // Handle complete response
        break;
      case 'error':
        // Handle error
        break;
    }
  }
}
```

## Rate Limiting و Error Handling

```typescript
class CoreAPIClient {
  private baseURL: string;
  private rateLimiter: RateLimiter;
  
  constructor(baseURL: string) {
    this.baseURL = baseURL;
    this.rateLimiter = new RateLimiter({
      tokensPerInterval: 60,
      interval: 'minute'
    });
  }
  
  async query(request: QueryRequest, token: string): Promise<QueryResponse> {
    // Check rate limit
    if (!await this.rateLimiter.consume(1)) {
      throw new Error('Rate limit exceeded');
    }
    
    try {
      const response = await this.fetchWithRetry(
        `${this.baseURL}/query`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(request)
        }
      );
      
      return response.json();
      
    } catch (error) {
      // Handle specific errors
      if (error.status === 429) {
        throw new Error('تعداد درخواست‌های شما بیش از حد مجاز است');
      } else if (error.status === 401) {
        throw new Error('احراز هویت نامعتبر است');
      } else if (error.status === 503) {
        throw new Error('سیستم موقتاً در دسترس نیست');
      }
      
      throw error;
    }
  }
  
  private async fetchWithRetry(
    url: string, 
    options: RequestInit, 
    retries = 3
  ): Promise<Response> {
    for (let i = 0; i < retries; i++) {
      try {
        const response = await fetch(url, options);
        if (response.ok) return response;
        
        if (response.status >= 500 && i < retries - 1) {
          // Exponential backoff
          await new Promise(resolve => 
            setTimeout(resolve, Math.pow(2, i) * 1000)
          );
          continue;
        }
        
        throw response;
      } catch (error) {
        if (i === retries - 1) throw error;
      }
    }
    
    throw new Error('Max retries exceeded');
  }
}
```

## نکات مهم برای UI/UX

### 1. نمایش وضعیت

```typescript
enum QueryStatus {
  IDLE = 'idle',
  LOADING = 'loading',
  STREAMING = 'streaming',
  SUCCESS = 'success',
  ERROR = 'error'
}

interface QueryState {
  status: QueryStatus;
  response?: QueryResponse;
  streamedText?: string;
  error?: string;
}
```

### 2. مدیریت حالت‌ها

```typescript
// React example
function useQuery() {
  const [state, setState] = useState<QueryState>({ 
    status: QueryStatus.IDLE 
  });
  
  const sendQuery = async (query: string) => {
    setState({ status: QueryStatus.LOADING });
    
    try {
      if (useStreaming) {
        setState({ status: QueryStatus.STREAMING, streamedText: '' });
        
        for await (const token of streamQuery(query, userToken)) {
          setState(prev => ({
            ...prev,
            streamedText: prev.streamedText + token
          }));
        }
        
        setState(prev => ({
          status: QueryStatus.SUCCESS,
          response: { ...prev.response, answer: prev.streamedText }
        }));
      } else {
        const response = await queryAPI(query, userToken);
        setState({ status: QueryStatus.SUCCESS, response });
      }
    } catch (error) {
      setState({ 
        status: QueryStatus.ERROR, 
        error: error.message 
      });
    }
  };
  
  return { state, sendQuery };
}
```

### 3. Cache Strategy

```typescript
class QueryCache {
  private cache: Map<string, QueryResponse> = new Map();
  private maxSize = 100;
  
  get(query: string): QueryResponse | null {
    const key = this.hashQuery(query);
    const cached = this.cache.get(key);
    
    if (cached && !this.isExpired(cached)) {
      return cached;
    }
    
    return null;
  }
  
  set(query: string, response: QueryResponse) {
    const key = this.hashQuery(query);
    
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
    
    this.cache.set(key, {
      ...response,
      cachedAt: Date.now()
    });
  }
  
  private hashQuery(query: string): string {
    return btoa(query.toLowerCase().trim());
  }
  
  private isExpired(response: any): boolean {
    const TTL = 3600000; // 1 hour
    return Date.now() - response.cachedAt > TTL;
  }
}
```

## Environment Variables

```bash
# .env for Users system

# Core API Configuration
VITE_CORE_API_URL=http://localhost:7001/api/v1
VITE_USERS_API_KEY=your-api-key-for-core

# Feature Flags
VITE_ENABLE_STREAMING=true
VITE_ENABLE_VOICE_SEARCH=true
VITE_ENABLE_IMAGE_SEARCH=true
VITE_ENABLE_OFFLINE_MODE=false

# UI Configuration
VITE_MAX_QUERY_LENGTH=2000
VITE_DEFAULT_LANGUAGE=fa
VITE_THEME=light
```

## Security Considerations

1. **Token Management**: ذخیره امن JWT tokens
2. **HTTPS**: استفاده از HTTPS در production
3. **CSP Headers**: تنظیم Content Security Policy
4. **Input Validation**: اعتبارسنجی ورودی‌ها قبل از ارسال
5. **XSS Protection**: پاکسازی محتوای دریافتی
6. **Rate Limiting**: محدودیت client-side هم اعمال شود

## Performance Tips

1. **Lazy Loading**: بارگذاری تدریجی مکالمات
2. **Virtual Scrolling**: برای لیست‌های طولانی
3. **Debouncing**: برای جستجوی real-time
4. **Prefetching**: پیش‌بارگذاری محتوای محتمل
5. **Service Worker**: برای cache و offline support
