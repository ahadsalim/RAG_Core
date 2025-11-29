# راهنمای یکپارچه‌سازی سیستم کاربران با RAG Core

## خلاصه

این سند راهنمای کامل پیاده‌سازی آپلود فایل در سیستم کاربران و ارسال لینک به RAG Core را ارائه می‌دهد.

---

## معماری پیشنهادی

```
┌─────────────┐      ┌──────────────────┐      ┌──────────────┐
│   کاربر     │ ───> │ سیستم کاربران    │ ───> │    MinIO     │
│  (Frontend) │      │   (Backend)      │      │  (Storage)   │
└─────────────┘      └──────────────────┘      └──────────────┘
                              │                        ▲
                              │ (لینک فایل)            │
                              ▼                        │
                     ┌──────────────────┐              │
                     │    RAG Core      │ ─────────────┘
                     │  (Processing)    │  (دانلود فایل)
                     └──────────────────┘
```

---

## بخش 1: پیاده‌سازی در سیستم کاربران (Backend)

### 1.1. نصب Dependencies

```bash
pip install boto3 python-multipart fastapi
```

### 1.2. پیکربندی MinIO

```python
# config/storage.py
import boto3
from botocore.exceptions import ClientError
import os
from datetime import datetime, timedelta
import uuid

class MinIOService:
    """سرویس مدیریت فایل در MinIO."""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=os.getenv('S3_ENDPOINT_URL'),
            aws_access_key_id=os.getenv('S3_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('S3_SECRET_ACCESS_KEY'),
            region_name=os.getenv('S3_REGION', 'us-east-1'),
            use_ssl=os.getenv('S3_USE_SSL', 'true').lower() == 'true'
        )
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'shared-storage')
        self.temp_prefix = "temp_uploads/"
        
    def upload_file(
        self,
        file_content: bytes,
        filename: str,
        user_id: str,
        content_type: str = 'application/octet-stream'
    ) -> dict:
        """
        آپلود فایل به MinIO.
        
        Returns:
            {
                'object_key': 'temp_uploads/user123/file.pdf',
                'filename': 'document.pdf',
                'size_bytes': 1024,
                'content_type': 'application/pdf',
                'expires_at': '2024-11-30T12:00:00'
            }
        """
        # تولید کلید یکتا
        file_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        object_key = f"{self.temp_prefix}{user_id}/{timestamp}_{file_id}_{filename}"
        
        # محاسبه زمان انقضا (24 ساعت)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Metadata
        metadata = {
            'user_id': user_id,
            'original_filename': filename,
            'upload_timestamp': datetime.utcnow().isoformat(),
            'expiration_date': expires_at.isoformat()
        }
        
        # آپلود به MinIO
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=object_key,
            Body=file_content,
            ContentType=content_type,
            Metadata=metadata
        )
        
        return {
            'object_key': object_key,
            'filename': filename,
            'size_bytes': len(file_content),
            'content_type': content_type,
            'expires_at': expires_at.isoformat()
        }
    
    def generate_presigned_url(
        self,
        object_key: str,
        expiration: int = 3600
    ) -> str:
        """
        تولید URL امن با زمان انقضا.
        
        Args:
            object_key: کلید فایل در MinIO
            expiration: زمان انقضا به ثانیه (پیش‌فرض 1 ساعت)
        """
        url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket_name,
                'Key': object_key
            },
            ExpiresIn=expiration
        )
        return url


# سرویس سراسری
minio_service = MinIOService()
```

### 1.3. API Endpoint برای آپلود فایل

```python
# api/upload.py
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from typing import List
from pydantic import BaseModel

router = APIRouter()

class FileUploadResponse(BaseModel):
    """پاسخ آپلود فایل."""
    object_key: str
    filename: str
    size_bytes: int
    content_type: str
    expires_at: str
    presigned_url: str = None  # اختیاری


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """
    آپلود فایل به MinIO.
    
    این endpoint فایل را دریافت کرده و در MinIO ذخیره می‌کند.
    سپس اطلاعات فایل (شامل object_key) را برمی‌گرداند.
    """
    # اعتبارسنجی
    if not file.filename:
        raise HTTPException(400, "Filename is required")
    
    # بررسی حجم فایل (حداکثر 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "File size exceeds 10MB limit")
    
    # بررسی نوع فایل
    allowed_types = [
        'image/jpeg', 'image/png', 'image/gif', 'image/bmp',
        'application/pdf', 'text/plain'
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"File type {file.content_type} not supported")
    
    # آپلود به MinIO
    from config.storage import minio_service
    
    result = minio_service.upload_file(
        file_content=content,
        filename=file.filename,
        user_id=str(current_user.id),
        content_type=file.content_type
    )
    
    # تولید presigned URL (اختیاری - برای امنیت بیشتر)
    # presigned_url = minio_service.generate_presigned_url(
    #     result['object_key'],
    #     expiration=3600
    # )
    # result['presigned_url'] = presigned_url
    
    return FileUploadResponse(**result)


@router.post("/upload-multiple")
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    current_user = Depends(get_current_user)
):
    """آپلود چند فایل همزمان (حداکثر 5)."""
    if len(files) > 5:
        raise HTTPException(400, "Maximum 5 files allowed")
    
    results = []
    for file in files:
        content = await file.read()
        
        # اعتبارسنجی
        if len(content) > 10 * 1024 * 1024:
            results.append({
                'filename': file.filename,
                'error': 'File size exceeds 10MB'
            })
            continue
        
        # آپلود
        try:
            from config.storage import minio_service
            result = minio_service.upload_file(
                file_content=content,
                filename=file.filename,
                user_id=str(current_user.id),
                content_type=file.content_type
            )
            results.append(result)
        except Exception as e:
            results.append({
                'filename': file.filename,
                'error': str(e)
            })
    
    return {'files': results}
```

### 1.4. API Endpoint برای ارسال Query به RAG Core

```python
# api/query.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import httpx

router = APIRouter()

class FileAttachment(BaseModel):
    """فایل ضمیمه."""
    filename: str
    minio_url: str  # object_key از MinIO
    file_type: str
    size_bytes: Optional[int] = None


class QueryRequest(BaseModel):
    """درخواست query با فایل‌های ضمیمه."""
    query: str
    file_attachments: Optional[List[FileAttachment]] = None
    language: str = "fa"
    max_results: int = 5


class QueryResponse(BaseModel):
    """پاسخ query."""
    answer: str
    sources: List[str]
    conversation_id: str
    message_id: str
    tokens_used: int
    processing_time_ms: int
    files_processed: Optional[int] = None


@router.post("/query", response_model=QueryResponse)
async def send_query_to_rag(
    request: QueryRequest,
    current_user = Depends(get_current_user)
):
    """
    ارسال query به RAG Core.
    
    این endpoint query کاربر و لینک‌های فایل را به RAG Core ارسال می‌کند.
    """
    # آماده‌سازی درخواست برای RAG Core
    rag_request = {
        "query": request.query,
        "language": request.language,
        "max_results": request.max_results,
        "file_attachments": [
            {
                "filename": f.filename,
                "minio_url": f.minio_url,
                "file_type": f.file_type,
                "size_bytes": f.size_bytes
            }
            for f in (request.file_attachments or [])
        ]
    }
    
    # ارسال به RAG Core
    rag_core_url = os.getenv('RAG_CORE_URL', 'http://rag-core:7001')
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{rag_core_url}/api/v1/query/v2",
                json=rag_request,
                headers={
                    "Authorization": f"Bearer {current_user.jwt_token}"
                },
                timeout=60.0
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"RAG Core error: {response.text}"
                )
            
            return QueryResponse(**response.json())
            
        except httpx.TimeoutException:
            raise HTTPException(504, "RAG Core timeout")
        except Exception as e:
            raise HTTPException(500, f"Failed to query RAG Core: {str(e)}")
```

---

## بخش 2: پیاده‌سازی در Frontend

### 2.1. React/Next.js Example

```typescript
// components/FileUploadQuery.tsx
import { useState } from 'react';
import axios from 'axios';

interface FileAttachment {
  filename: string;
  minio_url: string;
  file_type: string;
  size_bytes?: number;
}

export default function FileUploadQuery() {
  const [files, setFiles] = useState<File[]>([]);
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);

  // مرحله 1: آپلود فایل‌ها
  const uploadFiles = async (): Promise<FileAttachment[]> => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await axios.post('/api/upload-multiple', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });

    return response.data.files.map((f: any) => ({
      filename: f.filename,
      minio_url: f.object_key,
      file_type: f.content_type,
      size_bytes: f.size_bytes
    }));
  };

  // مرحله 2: ارسال query به RAG Core
  const sendQuery = async () => {
    setLoading(true);
    try {
      // آپلود فایل‌ها
      const fileAttachments = files.length > 0 
        ? await uploadFiles() 
        : undefined;

      // ارسال query
      const response = await axios.post('/api/query', {
        query,
        file_attachments: fileAttachments,
        language: 'fa',
        max_results: 5
      }, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      setAnswer(response.data.answer);
    } catch (error) {
      console.error('Error:', error);
      alert('خطا در پردازش درخواست');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold mb-4">پرسش با فایل ضمیمه</h2>
      
      {/* آپلود فایل */}
      <div className="mb-4">
        <label className="block mb-2">فایل‌ها (حداکثر 5):</label>
        <input
          type="file"
          multiple
          accept=".jpg,.jpeg,.png,.pdf,.txt"
          onChange={(e) => setFiles(Array.from(e.target.files || []))}
          className="border p-2 w-full"
        />
        {files.length > 0 && (
          <p className="text-sm text-gray-600 mt-1">
            {files.length} فایل انتخاب شده
          </p>
        )}
      </div>

      {/* سوال */}
      <div className="mb-4">
        <label className="block mb-2">سوال:</label>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="سوال خود را بنویسید..."
          className="border p-2 w-full h-24"
        />
      </div>

      {/* دکمه ارسال */}
      <button
        onClick={sendQuery}
        disabled={loading || !query}
        className="bg-blue-500 text-white px-4 py-2 rounded disabled:bg-gray-300"
      >
        {loading ? 'در حال پردازش...' : 'ارسال'}
      </button>

      {/* نمایش پاسخ */}
      {answer && (
        <div className="mt-4 p-4 bg-gray-100 rounded">
          <h3 className="font-bold mb-2">پاسخ:</h3>
          <p className="whitespace-pre-wrap">{answer}</p>
        </div>
      )}
    </div>
  );
}
```

### 2.2. Vue.js Example

```vue
<template>
  <div class="file-upload-query">
    <h2>پرسش با فایل ضمیمه</h2>
    
    <!-- آپلود فایل -->
    <div class="file-input">
      <label>فایل‌ها (حداکثر 5):</label>
      <input
        type="file"
        multiple
        accept=".jpg,.jpeg,.png,.pdf,.txt"
        @change="handleFileSelect"
      />
      <p v-if="files.length">{{ files.length }} فایل انتخاب شده</p>
    </div>

    <!-- سوال -->
    <div class="query-input">
      <label>سوال:</label>
      <textarea
        v-model="query"
        placeholder="سوال خود را بنویسید..."
      />
    </div>

    <!-- دکمه ارسال -->
    <button
      @click="sendQuery"
      :disabled="loading || !query"
    >
      {{ loading ? 'در حال پردازش...' : 'ارسال' }}
    </button>

    <!-- نمایش پاسخ -->
    <div v-if="answer" class="answer">
      <h3>پاسخ:</h3>
      <p>{{ answer }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import axios from 'axios';

const files = ref([]);
const query = ref('');
const answer = ref('');
const loading = ref(false);

const handleFileSelect = (event) => {
  files.value = Array.from(event.target.files);
};

const uploadFiles = async () => {
  const formData = new FormData();
  files.value.forEach(file => {
    formData.append('files', file);
  });

  const response = await axios.post('/api/upload-multiple', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
      'Authorization': `Bearer ${localStorage.getItem('token')}`
    }
  });

  return response.data.files.map(f => ({
    filename: f.filename,
    minio_url: f.object_key,
    file_type: f.content_type,
    size_bytes: f.size_bytes
  }));
};

const sendQuery = async () => {
  loading.value = true;
  try {
    const fileAttachments = files.value.length > 0 
      ? await uploadFiles() 
      : undefined;

    const response = await axios.post('/api/query', {
      query: query.value,
      file_attachments: fileAttachments,
      language: 'fa',
      max_results: 5
    }, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });

    answer.value = response.data.answer;
  } catch (error) {
    console.error('Error:', error);
    alert('خطا در پردازش درخواست');
  } finally {
    loading.value = false;
  }
};
</script>
```

---

## بخش 3: تنظیمات Environment

### 3.1. سیستم کاربران (.env)

```bash
# MinIO Configuration
S3_ENDPOINT_URL=http://minio-server:9000
S3_ACCESS_KEY_ID=your_access_key_here
S3_SECRET_ACCESS_KEY=your_secret_key_here
S3_BUCKET_NAME=shared-storage
S3_REGION=us-east-1
S3_USE_SSL=true

# RAG Core URL
RAG_CORE_URL=http://rag-core:7001
```

### 3.2. RAG Core (.env)

```bash
# MinIO Configuration (همان تنظیمات)
S3_ENDPOINT_URL=http://minio-server:9000
S3_ACCESS_KEY_ID=your_access_key_here
S3_SECRET_ACCESS_KEY=your_secret_key_here
S3_BUCKET_NAME=shared-storage
S3_REGION=us-east-1
S3_USE_SSL=true
```

---

## بخش 4: تست و بررسی

### 4.1. تست آپلود فایل

```bash
# تست آپلود یک فایل
curl -X POST "http://users-api/api/upload" \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@document.pdf"

# پاسخ:
# {
#   "object_key": "temp_uploads/user123/20241129_120000_abc_document.pdf",
#   "filename": "document.pdf",
#   "size_bytes": 1024000,
#   "content_type": "application/pdf",
#   "expires_at": "2024-11-30T12:00:00"
# }
```

### 4.2. تست Query با فایل

```bash
curl -X POST "http://users-api/api/query" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "این سند چه می‌گوید؟",
    "file_attachments": [{
      "filename": "document.pdf",
      "minio_url": "temp_uploads/user123/20241129_120000_abc_document.pdf",
      "file_type": "application/pdf"
    }]
  }'
```

---

## نتیجه‌گیری

با این پیاده‌سازی:

✅ فایل‌ها فقط یک‌بار آپلود می‌شوند (به سیستم کاربران)  
✅ RAG Core فقط لینک دریافت می‌کند  
✅ کاهش چشمگیر traffic شبکه  
✅ مدیریت متمرکز فایل‌ها  
✅ امنیت و کنترل دسترسی بهتر  

این رویکرد برای production آماده است و مقیاس‌پذیری عالی دارد.
