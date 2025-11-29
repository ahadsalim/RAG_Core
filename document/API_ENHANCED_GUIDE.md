# راهنمای API پیشرفته - سیستم کاربران

**نسخه:** 2.0.0  
**تاریخ:** 2025-11-29  
**مخاطب:** تیم توسعه سیستم Users

---

## 🎯 خلاصه تغییرات

API سوال‌پاسخ به‌روز شده و قابلیت‌های جدید اضافه شده:

### ✨ قابلیت‌های جدید

1. **تحلیل فایل با LLM** - فایل‌های ضمیمه قبل از پردازش تحلیل می‌شوند
2. **حافظه کوتاه‌مدت** - 10 پیام آخر در پاسخ‌دهی لحاظ می‌شود
3. **حافظه بلندمدت** - خلاصه مکالمات قبلی ذخیره و استفاده می‌شود
4. **کلاسیفیکیشن هوشمند** - با در نظر گرفتن context و فایل‌ها
5. **پاسخ‌دهی بهتر** - با استفاده از تمام context موجود

---

## 📡 Endpoint

```
POST https://rag-core:7001/api/v1/query/
Content-Type: application/json
Authorization: Bearer {JWT_TOKEN}
```

---

## 📥 Request Format

### ساختار کامل

```json
{
  "query": "سوال کاربر",
  "conversation_id": "uuid-optional",
  "language": "fa",
  "max_results": 5,
  "filters": {},
  "use_cache": true,
  "use_reranking": true,
  "stream": false,
  "user_preferences": {},
  "file_attachments": [
    {
      "filename": "document.pdf",
      "minio_url": "temp_uploads/user123/20231129_120000_uuid_document.pdf",
      "file_type": "application/pdf",
      "size_bytes": 1024000
    }
  ]
}
```

### پارامترها

#### الزامی

- **`query`** (string, 1-2000 کاراکتر)
  - سوال کاربر
  - مثال: `"قانون کار در مورد مرخصی چه می‌گوید؟"`

#### اختیاری

- **`conversation_id`** (string, UUID)
  - ID مکالمه برای ادامه گفتگو
  - اگر ارسال نشود، مکالمه جدید ایجاد می‌شود
  - **مهم:** برای استفاده از حافظه، حتماً ارسال کنید

- **`language`** (string, default: "fa")
  - زبان سوال: `fa`, `en`, `ar`

- **`max_results`** (integer, 1-20, default: 5)
  - تعداد منابع برای جستجو

- **`file_attachments`** (array, max 5 items)
  - لیست فایل‌های ضمیمه از MinIO
  - هر فایل شامل:
    - `filename`: نام فایل
    - `minio_url`: object key در MinIO (باکت temp-userfile)
    - `file_type`: MIME type
    - `size_bytes`: حجم فایل (اختیاری)

- **`use_cache`** (boolean, default: true)
  - استفاده از cache برای سرعت بیشتر

- **`use_reranking`** (boolean, default: true)
  - مرتب‌سازی مجدد نتایج برای دقت بیشتر

- **`stream`** (boolean, default: false)
  - دریافت پاسخ به صورت stream

---

## 📤 Response Format

```json
{
  "answer": "طبق ماده 64 قانون کار، کارگر حق دارد...",
  "sources": [
    "dee1acff-8131-49ec-b7ed-78d543dcc539",
    "abc123-456-789..."
  ],
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_id": "660e8400-e29b-41d4-a716-446655440001",
  "tokens_used": 1250,
  "processing_time_ms": 3500,
  "file_analysis": "فایل ضمیمه شده یک قرارداد کار است که...",
  "context_used": true
}
```

### فیلدهای پاسخ

- **`answer`** - پاسخ تولید شده
- **`sources`** - لیست ID منابع استفاده شده
- **`conversation_id`** - ID مکالمه (برای ادامه گفتگو)
- **`message_id`** - ID پیام فعلی
- **`tokens_used`** - تعداد توکن‌های مصرف شده
- **`processing_time_ms`** - زمان پردازش (میلی‌ثانیه)
- **`file_analysis`** - تحلیل فایل‌ها (اگر فایل ارسال شده باشد)
- **`context_used`** - آیا از حافظه استفاده شد؟

---

## 🔄 فرآیند پردازش (جدید)

```
1. احراز هویت کاربر
   ↓
2. بررسی محدودیت روزانه
   ↓
3. دریافت/ایجاد Conversation
   ↓
4. تحلیل فایل‌های ضمیمه با LLM ← جدید!
   ↓
5. دریافت حافظه بلندمدت (خلاصه مکالمات) ← جدید!
   ↓
6. دریافت حافظه کوتاه‌مدت (10 پیام آخر) ← جدید!
   ↓
7. کلاسیفیکیشن سوال (با context) ← بهبود یافته!
   ↓
8. ساخت Context کامل ← جدید!
   ↓
9. پردازش با RAG Pipeline
   ↓
10. ذخیره پیام‌ها
   ↓
11. به‌روزرسانی حافظه بلندمدت (Background) ← جدید!
   ↓
12. برگرداندن پاسخ
```

---

## 💡 نکات مهم برای پیاده‌سازی

### 1. ارسال Conversation ID

**قبل:**
```javascript
// هر بار conversation_id جدید
const response = await fetch('/api/v1/query/', {
  method: 'POST',
  body: JSON.stringify({
    query: "سوال من"
    // conversation_id ارسال نمی‌شد
  })
});
```

**حالا (صحیح):**
```javascript
// ذخیره conversation_id برای استفاده مجدد
let conversationId = localStorage.getItem('current_conversation_id');

const response = await fetch('/api/v1/query/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    query: "سوال من",
    conversation_id: conversationId  // ← مهم!
  })
});

const data = await response.json();

// ذخیره برای سوال بعدی
if (!conversationId) {
  localStorage.setItem('current_conversation_id', data.conversation_id);
}
```

### 2. آپلود فایل به MinIO

**مراحل:**

```javascript
// 1. آپلود فایل به MinIO (باکت temp-userfile)
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const uploadResponse = await fetch('YOUR_MINIO_UPLOAD_ENDPOINT', {
  method: 'POST',
  body: formData
});

const uploadData = await uploadResponse.json();
const minioUrl = uploadData.object_key;  // مثال: "temp_uploads/user123/..."

// 2. ارسال سوال با لینک فایل
const queryResponse = await fetch('/api/v1/query/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    query: "این سند را تحلیل کن",
    conversation_id: conversationId,
    file_attachments: [
      {
        filename: fileInput.files[0].name,
        minio_url: minioUrl,
        file_type: fileInput.files[0].type,
        size_bytes: fileInput.files[0].size
      }
    ]
  })
});
```

### 3. نمایش تحلیل فایل

```javascript
const data = await response.json();

// نمایش تحلیل فایل (اگر وجود داشت)
if (data.file_analysis) {
  console.log("تحلیل فایل:", data.file_analysis);
  // نمایش در UI
  showFileAnalysis(data.file_analysis);
}

// نمایش پاسخ
showAnswer(data.answer);

// نمایش اینکه آیا از حافظه استفاده شد
if (data.context_used) {
  console.log("از مکالمات قبلی استفاده شد");
}
```

---

## 📝 مثال‌های کامل

### مثال 1: سوال ساده (بدون فایل)

```bash
curl -X POST "https://rag-core:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "قانون کار در مورد مرخصی چه می‌گوید؟",
    "language": "fa"
  }'
```

### مثال 2: ادامه مکالمه (با حافظه)

```bash
curl -X POST "https://rag-core:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "چند روز مرخصی حق دارم؟",
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "language": "fa"
  }'
```

**توجه:** سیستم از مکالمه قبلی می‌داند که موضوع "قانون کار" است.

### مثال 3: سوال با فایل ضمیمه

```bash
curl -X POST "https://rag-core:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "این قرارداد را بررسی کن و نکات مهم را بگو",
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "language": "fa",
    "file_attachments": [
      {
        "filename": "contract.pdf",
        "minio_url": "temp_uploads/user123/20231129_120000_uuid_contract.pdf",
        "file_type": "application/pdf",
        "size_bytes": 524288
      }
    ]
  }'
```

### مثال 4: چند فایل همزمان

```bash
curl -X POST "https://rag-core:7001/api/v1/query/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type": "application/json" \
  -d '{
    "query": "این اسناد را با هم مقایسه کن",
    "file_attachments": [
      {
        "filename": "contract_v1.pdf",
        "minio_url": "temp_uploads/user123/file1.pdf",
        "file_type": "application/pdf"
      },
      {
        "filename": "contract_v2.pdf",
        "minio_url": "temp_uploads/user123/file2.pdf",
        "file_type": "application/pdf"
      }
    ]
  }'
```

---

## ⚠️ خطاهای رایج

### 1. فراموش کردن conversation_id

**مشکل:** هر سوال به عنوان مکالمه جدید در نظر گرفته می‌شود

**راه‌حل:** همیشه conversation_id را ذخیره و ارسال کنید

### 2. فایل در MinIO موجود نیست

**خطا:**
```json
{
  "detail": "File not found in MinIO"
}
```

**راه‌حل:** 
- مطمئن شوید فایل در باکت `temp-userfile` آپلود شده
- object_key را صحیح ارسال کنید

### 3. محدودیت روزانه

**خطا:**
```json
{
  "detail": "Daily query limit exceeded"
}
```

**راه‌حل:** کاربر باید تا فردا صبر کند یا limit افزایش یابد

---

## 🔧 تنظیمات پیشنهادی

### برای UI بهتر

```javascript
// نمایش typing indicator
showTypingIndicator();

// ارسال درخواست
const response = await sendQuery(query, conversationId, files);

// مخفی کردن typing indicator
hideTypingIndicator();

// نمایش پاسخ
if (response.file_analysis) {
  showFileAnalysisSection(response.file_analysis);
}
showAnswer(response.answer);

// نمایش منابع
showSources(response.sources);

// نمایش اطلاعات
showMetadata({
  tokens: response.tokens_used,
  time: response.processing_time_ms,
  contextUsed: response.context_used
});
```

---

## 📊 مقایسه نسخه قدیم و جدید

| ویژگی | نسخه قدیم | نسخه جدید |
|-------|----------|-----------|
| تحلیل فایل | فقط استخراج متن | تحلیل هوشمند با LLM ✨ |
| حافظه مکالمه | ندارد | کوتاه‌مدت + بلندمدت ✨ |
| کلاسیفیکیشن | بدون context | با context و فایل ✨ |
| پاسخ‌دهی | بدون context قبلی | با تمام context ✨ |
| سرعت | سریع | کمی کندتر (به دلیل تحلیل) |

---

## 🚀 مراحل پیاده‌سازی

### مرحله 1: به‌روزرسانی کد ارسال

```javascript
// قبل
sendQuery(query) {
  return fetch('/api/v1/query/', {
    method: 'POST',
    body: JSON.stringify({ query })
  });
}

// بعد
sendQuery(query, conversationId, files = []) {
  return fetch('/api/v1/query/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${this.token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      query,
      conversation_id: conversationId,
      file_attachments: files
    })
  });
}
```

### مرحله 2: مدیریت Conversation

```javascript
class ConversationManager {
  constructor() {
    this.currentConversationId = null;
  }
  
  startNew() {
    this.currentConversationId = null;
  }
  
  async sendMessage(query, files = []) {
    const response = await sendQuery(
      query,
      this.currentConversationId,
      files
    );
    
    const data = await response.json();
    
    // ذخیره conversation_id
    if (!this.currentConversationId) {
      this.currentConversationId = data.conversation_id;
    }
    
    return data;
  }
}
```

### مرحله 3: تست

```javascript
const manager = new ConversationManager();

// سوال اول
const response1 = await manager.sendMessage("قانون کار چیست؟");
console.log(response1.answer);

// سوال دوم (با حافظه)
const response2 = await manager.sendMessage("چند ماده دارد؟");
console.log(response2.answer);  // سیستم می‌داند منظور "قانون کار" است

// سوال با فایل
const response3 = await manager.sendMessage(
  "این قرارداد را بررسی کن",
  [{ filename: "contract.pdf", minio_url: "...", file_type: "application/pdf" }]
);
console.log(response3.file_analysis);  // تحلیل فایل
console.log(response3.answer);  // پاسخ
```

---

## 📞 پشتیبانی

اگر سوال یا مشکلی دارید:
- **تیم Backend Core**
- **مستندات کامل:** `/srv/document/1_CORE_SYSTEM_DOCUMENTATION.md`

---

**تاریخ به‌روزرسانی:** 2025-11-29  
**نسخه API:** 2.0.0
