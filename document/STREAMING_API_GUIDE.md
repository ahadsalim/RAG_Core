# 📡 راهنمای API استریم (Streaming)

## 🎯 خلاصه

API جدید برای دریافت پاسخ به صورت **تدریجی و لحظه‌ای** (مانند ChatGPT).

---

## 🔗 Endpoint

```
POST https://core.tejarat.chat/api/v1/query/query_stream
```

**توجه:** این endpoint جدا از endpoint اصلی (`/api/v1/query/`) است و به موازات آن کار می‌کند.

---

## 📥 Request (درخواست)

### Headers
```http
Content-Type: application/json
Authorization: Bearer YOUR_JWT_TOKEN
```

### Body (بدنه درخواست)
```json
{
  "query": "قانون کار در مورد مرخصی استعلاجی چه می‌گوید؟",
  "conversation_id": "uuid-optional",
  "language": "fa",
  "stream": true,
  "file_attachments": [
    {
      "filename": "contract.pdf",
      "minio_url": "https://minio.example.com/temp/file.pdf",
      "file_type": "application/pdf",
      "size_bytes": 12345
    }
  ]
}
```

**نکته:** فیلد `stream` اختیاری است و فقط برای سازگاری با API قدیمی است.

---

## 📤 Response (پاسخ)

پاسخ به صورت **Server-Sent Events (SSE)** ارسال می‌شود.

### نوع پیام‌ها

#### 1️⃣ `conversation_id` - شناسه مکالمه
```json
{
  "type": "conversation_id",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### 2️⃣ `status` - وضعیت پردازش
```json
{
  "type": "status",
  "message": "در حال تحلیل فایل‌ها..."
}
```

یا:
```json
{
  "type": "status",
  "message": "در حال جستجو در منابع..."
}
```

یا:
```json
{
  "type": "status",
  "message": "5 منبع یافت شد"
}
```

یا:
```json
{
  "type": "status",
  "message": "در حال تولید پاسخ..."
}
```

#### 3️⃣ `file_analysis` - تحلیل فایل‌ها
```json
{
  "type": "file_analysis",
  "content": "📄 contract.pdf:\nاین قرارداد یک قرارداد کار است که شامل..."
}
```

#### 4️⃣ `classification` - دسته‌بندی سوال
```json
{
  "type": "classification",
  "category": "business_with_file",
  "confidence": 0.95
}
```

**دسته‌ها:**
- `invalid_no_file`: سوال نامفهوم بدون فایل
- `invalid_with_file`: سوال نامفهوم با فایل
- `general_no_business`: سوال عمومی (مثل "سلام")
- `business_no_file`: سوال کسب‌وکار بدون فایل
- `business_with_file`: سوال کسب‌وکار با فایل

#### 5️⃣ `token` - هر کلمه/توکن از پاسخ
```json
{
  "type": "token",
  "content": "طبق"
}
```

```json
{
  "type": "token",
  "content": " ماده"
}
```

```json
{
  "type": "token",
  "content": " ۷۴"
}
```

**نکته:** این پیام‌ها پشت سر هم ارسال می‌شوند تا پاسخ کامل شود.

#### 6️⃣ `done` - اتمام پاسخ
```json
{
  "type": "done",
  "message_id": "660e8400-e29b-41d4-a716-446655440000",
  "processing_time_ms": 3500,
  "sources": [
    "قانون کار جمهوری اسلامی ایران",
    "آیین‌نامه اجرایی قانون کار"
  ]
}
```

#### 7️⃣ `error` - خطا
```json
{
  "type": "error",
  "message": "Failed to process query: Connection timeout"
}
```

---

## 💻 نمونه کد (JavaScript/TypeScript)

### روش 1: با EventSource (ساده‌تر)

**⚠️ محدودیت:** EventSource فقط از GET پشتیبانی می‌کند، برای POST باید از fetch استفاده کنید.

### روش 2: با fetch (پیشنهادی)

```javascript
async function streamQuery(query, conversationId = null) {
  const response = await fetch('https://core.tejarat.chat/api/v1/query/query_stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${YOUR_JWT_TOKEN}`
    },
    body: JSON.stringify({
      query: query,
      conversation_id: conversationId,
      language: 'fa',
      stream: true
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let fullAnswer = '';
  let conversationId = null;
  let sources = [];

  while (true) {
    const { done, value } = await reader.read();
    
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // Keep incomplete line in buffer
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        
        switch (data.type) {
          case 'conversation_id':
            conversationId = data.conversation_id;
            console.log('Conversation ID:', conversationId);
            break;
            
          case 'status':
            console.log('Status:', data.message);
            // نمایش وضعیت در UI
            showStatus(data.message);
            break;
            
          case 'file_analysis':
            console.log('File Analysis:', data.content);
            // نمایش تحلیل فایل
            showFileAnalysis(data.content);
            break;
            
          case 'classification':
            console.log('Category:', data.category, 'Confidence:', data.confidence);
            break;
            
          case 'token':
            fullAnswer += data.content;
            // نمایش تدریجی پاسخ
            updateAnswer(fullAnswer);
            break;
            
          case 'done':
            sources = data.sources;
            console.log('Done! Message ID:', data.message_id);
            console.log('Processing time:', data.processing_time_ms, 'ms');
            console.log('Sources:', sources);
            // نمایش منابع
            showSources(sources);
            break;
            
          case 'error':
            console.error('Error:', data.message);
            showError(data.message);
            break;
        }
      }
    }
  }
  
  return {
    answer: fullAnswer,
    conversationId: conversationId,
    sources: sources
  };
}

// استفاده
streamQuery('قانون کار در مورد مرخصی استعلاجی چه می‌گوید؟')
  .then(result => {
    console.log('Final answer:', result.answer);
    console.log('Conversation ID:', result.conversationId);
    console.log('Sources:', result.sources);
  })
  .catch(error => {
    console.error('Stream failed:', error);
  });
```

---

## 🎨 نمونه کد React

```typescript
import { useState, useCallback } from 'react';

interface StreamMessage {
  type: string;
  content?: string;
  message?: string;
  category?: string;
  confidence?: number;
  conversation_id?: string;
  message_id?: string;
  processing_time_ms?: number;
  sources?: string[];
}

function useStreamQuery() {
  const [answer, setAnswer] = useState('');
  const [status, setStatus] = useState('');
  const [sources, setSources] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const streamQuery = useCallback(async (query: string, convId?: string) => {
    setIsStreaming(true);
    setAnswer('');
    setStatus('');
    setSources([]);

    try {
      const response = await fetch('https://core.tejarat.chat/api/v1/query/query_stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          query,
          conversation_id: convId,
          language: 'fa',
          stream: true
        })
      });

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data: StreamMessage = JSON.parse(line.slice(6));

            switch (data.type) {
              case 'conversation_id':
                setConversationId(data.conversation_id!);
                break;
              case 'status':
                setStatus(data.message!);
                break;
              case 'token':
                setAnswer(prev => prev + data.content);
                break;
              case 'done':
                setSources(data.sources || []);
                setStatus('');
                break;
              case 'error':
                throw new Error(data.message);
            }
          }
        }
      }
    } catch (error) {
      console.error('Stream error:', error);
      throw error;
    } finally {
      setIsStreaming(false);
    }
  }, []);

  return {
    answer,
    status,
    sources,
    isStreaming,
    conversationId,
    streamQuery
  };
}

// استفاده در کامپوننت
function ChatComponent() {
  const { answer, status, sources, isStreaming, streamQuery } = useStreamQuery();

  const handleSubmit = async (query: string) => {
    await streamQuery(query);
  };

  return (
    <div>
      {status && <div className="status">{status}</div>}
      
      <div className="answer">
        {answer}
        {isStreaming && <span className="cursor">▊</span>}
      </div>
      
      {sources.length > 0 && (
        <div className="sources">
          <h4>منابع:</h4>
          <ul>
            {sources.map((source, i) => (
              <li key={i}>{source}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

---

## 🎨 نمونه کد Vue.js

```vue
<template>
  <div class="chat-container">
    <div v-if="status" class="status">{{ status }}</div>
    
    <div class="answer">
      {{ answer }}
      <span v-if="isStreaming" class="cursor">▊</span>
    </div>
    
    <div v-if="sources.length > 0" class="sources">
      <h4>منابع:</h4>
      <ul>
        <li v-for="(source, i) in sources" :key="i">{{ source }}</li>
      </ul>
    </div>
    
    <input 
      v-model="query" 
      @keyup.enter="handleSubmit"
      placeholder="سوال خود را بپرسید..."
    />
  </div>
</template>

<script setup>
import { ref } from 'vue';

const query = ref('');
const answer = ref('');
const status = ref('');
const sources = ref([]);
const isStreaming = ref(false);
const conversationId = ref(null);

async function handleSubmit() {
  if (!query.value.trim()) return;
  
  isStreaming.value = true;
  answer.value = '';
  status.value = '';
  sources.value = [];
  
  try {
    const response = await fetch('https://core.tejarat.chat/api/v1/query/query_stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({
        query: query.value,
        conversation_id: conversationId.value,
        language: 'fa',
        stream: true
      })
    });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          
          switch (data.type) {
            case 'conversation_id':
              conversationId.value = data.conversation_id;
              break;
            case 'status':
              status.value = data.message;
              break;
            case 'token':
              answer.value += data.content;
              break;
            case 'done':
              sources.value = data.sources || [];
              status.value = '';
              break;
            case 'error':
              throw new Error(data.message);
          }
        }
      }
    }
  } catch (error) {
    console.error('Stream error:', error);
    alert('خطا در دریافت پاسخ');
  } finally {
    isStreaming.value = false;
  }
  
  query.value = '';
}
</script>

<style scoped>
.cursor {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
</style>
```

---

## ⚡ مزایای Streaming

1. **تجربه کاربری بهتر:** کاربر بلافاصله شروع به دیدن پاسخ می‌کند
2. **کاهش زمان انتظار ظاهری:** حتی اگر پاسخ کامل 10 ثانیه طول بکشد، کاربر از ثانیه اول پاسخ را می‌بیند
3. **نمایش پیشرفت:** وضعیت‌های مختلف (تحلیل فایل، جستجو، تولید پاسخ) به کاربر نمایش داده می‌شود
4. **مانند ChatGPT:** تجربه‌ای مشابه ChatGPT و سایر AI چت‌بات‌ها

---

## 🔄 مقایسه با API عادی

| ویژگی | API عادی (`/query/`) | API استریم (`/query/query_stream`) |
|-------|---------------------|------------------------------|
| نوع پاسخ | JSON یکجا | Server-Sent Events تدریجی |
| زمان انتظار | کل پاسخ را منتظر بمانید | بلافاصله شروع می‌شود |
| تجربه کاربری | انتظار → پاسخ کامل | پاسخ تدریجی (مانند ChatGPT) |
| نمایش وضعیت | ❌ خیر | ✅ بله |
| پیچیدگی کد | ساده‌تر | کمی پیچیده‌تر |
| مناسب برای | پاسخ‌های کوتاه | پاسخ‌های بلند |

---

## 🛠️ نکات فنی

1. **Content-Type:** پاسخ از نوع `text/event-stream` است
2. **Headers مهم:**
   - `Cache-Control: no-cache`
   - `Connection: keep-alive`
   - `X-Accel-Buffering: no`
3. **فرمت پیام:** هر پیام با `data: ` شروع می‌شود و با `\n\n` تمام می‌شود
4. **Encoding:** UTF-8 (پشتیبانی کامل از فارسی)

---

## ❓ سوالات متداول

### 1. آیا باید از streaming استفاده کنم؟
- **بله** اگر می‌خواهید تجربه کاربری بهتری داشته باشید
- **خیر** اگر فقط به پاسخ نهایی نیاز دارید و UI ساده‌تری می‌خواهید

### 2. آیا می‌توانم هر دو را استفاده کنم؟
- بله! می‌توانید برای برخی سوالات از streaming و برای برخی از API عادی استفاده کنید

### 3. آیا streaming سریع‌تر است؟
- زمان کل یکسان است، اما **زمان انتظار ظاهری** کمتر است

### 4. آیا با فایل‌ها کار می‌کند؟
- بله! کاملاً پشتیبانی می‌شود

### 5. آیا حافظه مکالمات را حفظ می‌کند؟
- بله! مانند API عادی

---

## 📞 پشتیبانی

اگر سوالی دارید، با تیم Core تماس بگیرید.

**موفق باشید!** 🚀
