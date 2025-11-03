# راهنمای استفاده از Local Embedding

## 🎯 مدل نصب شده

**مدل**: `intfloat/multilingual-e5-base`
- **بُعد**: 768
- **زبان‌ها**: فارسی، انگلیسی، عربی، و 100+ زبان دیگر
- **حجم**: 1.1 GB
- **دستگاه**: CPU (یا GPU اگر CUDA موجود باشد)

---

## 🚀 API Endpoints

### 1️⃣ دریافت اطلاعات مدل

```bash
curl http://localhost:7001/api/v1/embeddings/info
```

**خروجی**:
```json
{
    "model": "intfloat/multilingual-e5-base",
    "dimension": 768,
    "device": "cpu",
    "status": "ready"
}
```

---

### 2️⃣ ساخت Embedding (یک متن)

```bash
curl -X POST http://localhost:7001/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": "قانون کار ایران"
  }'
```

**خروجی**:
```json
{
    "object": "list",
    "data": [
        {
            "object": "embedding",
            "embedding": [0.034, -0.021, ...],  // 768 عدد
            "index": 0
        }
    ],
    "model": "intfloat/multilingual-e5-base",
    "usage": {
        "prompt_tokens": 5,
        "total_tokens": 5
    }
}
```

---

### 3️⃣ ساخت Embedding (چند متن)

```bash
curl -X POST http://localhost:7001/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
        "قانون کار ایران",
        "قوانین استخدامی",
        "حقوق کارگران"
    ]
  }'
```

---

### 4️⃣ محاسبه شباهت (Similarity)

```bash
curl -X POST http://localhost:7001/api/v1/embeddings/similarity \
  -H "Content-Type: application/json" \
  -d '{
    "text1": "قانون کار ایران",
    "text2": "قوانین استخدامی در ایران"
  }'
```

**خروجی**:
```json
{
    "text1": "قانون کار ایران",
    "text2": "قوانین استخدامی در ایران",
    "similarity": 0.9293810725212097,
    "model": "intfloat/multilingual-e5-base"
}
```

**نکته**: Similarity بین -1 تا 1 است:
- `1.0` = کاملاً مشابه
- `0.0` = بی‌ربط
- `-1.0` = کاملاً مخالف

---

## 🐍 استفاده در Python

### نصب کتابخانه:
```bash
pip install requests
```

### ساخت Embedding:
```python
import requests
import numpy as np

def get_embedding(text: str) -> np.ndarray:
    """دریافت embedding برای یک متن."""
    response = requests.post(
        "http://localhost:7001/api/v1/embeddings",
        json={"input": text}
    )
    
    data = response.json()
    embedding = np.array(data["data"][0]["embedding"])
    
    return embedding


# مثال
embedding = get_embedding("قانون کار ایران")
print(f"Dimension: {len(embedding)}")
print(f"First 5 values: {embedding[:5]}")
```

### محاسبه Similarity:
```python
def calculate_similarity(text1: str, text2: str) -> float:
    """محاسبه شباهت بین دو متن."""
    response = requests.post(
        "http://localhost:7001/api/v1/embeddings/similarity",
        json={"text1": text1, "text2": text2}
    )
    
    data = response.json()
    return data["similarity"]


# مثال
similarity = calculate_similarity(
    "قانون کار ایران",
    "قوانین استخدامی"
)
print(f"Similarity: {similarity:.4f}")
```

### Embedding چندین متن:
```python
def get_batch_embeddings(texts: list[str]) -> np.ndarray:
    """دریافت embedding برای چندین متن."""
    response = requests.post(
        "http://localhost:7001/api/v1/embeddings",
        json={"input": texts}
    )
    
    data = response.json()
    embeddings = [np.array(item["embedding"]) for item in data["data"]]
    
    return np.array(embeddings)


# مثال
texts = ["قانون کار", "قوانین مالیاتی", "حقوق کارگران"]
embeddings = get_batch_embeddings(texts)
print(f"Shape: {embeddings.shape}")  # (3, 768)
```

---

## 🔧 استفاده مستقیم در کد

می‌توانید مستقیماً از سرویس استفاده کنید:

```python
from app.services.local_embedding_service import get_local_embedding_service

# دریافت سرویس
embedding_service = get_local_embedding_service()

# یک متن
embedding = embedding_service.encode_single("قانون کار ایران")
print(f"Shape: {embedding.shape}")  # (768,)

# چند متن
texts = ["متن ۱", "متن ۲", "متن ۳"]
embeddings = embedding_service.encode(texts)
print(f"Shape: {embeddings.shape}")  # (3, 768)

# محاسبه شباهت
similarity = embedding_service.similarity(embeddings[0], embeddings[1])
print(f"Similarity: {similarity}")
```

---

## 🌐 استفاده از پروژه Ingest

در پروژه Ingest، می‌توانید از این endpoint استفاده کنید:

### تنظیم .env در Ingest:
```bash
# در /home/ahad/project/ingest/.env
EMBEDDING_BASE_URL="http://localhost:7001/api/v1"
EMBEDDING_MODEL="intfloat/multilingual-e5-base"
```

### کد Python در Ingest:
```python
import requests

def get_embeddings_from_core(texts: list[str]):
    """دریافت embeddings از Core API."""
    response = requests.post(
        "http://localhost:7001/api/v1/embeddings",
        json={"input": texts}
    )
    
    data = response.json()
    embeddings = [item["embedding"] for item in data["data"]]
    
    return embeddings
```

---

## 📊 سازگاری با OpenAI API

این endpoint کاملاً سازگار با OpenAI Embedding API است:

```python
# به جای OpenAI:
from openai import OpenAI
client = OpenAI(api_key="...")
response = client.embeddings.create(
    input="قانون کار",
    model="text-embedding-3-large"
)

# می‌توانید از Core استفاده کنید:
from openai import OpenAI
client = OpenAI(
    api_key="not-needed",
    base_url="http://localhost:7001/api/v1"
)
response = client.embeddings.create(
    input="قانون کار",
    model="intfloat/multilingual-e5-base"
)
```

---

## 🚀 بهینه‌سازی عملکرد

### 1. استفاده از GPU (اگر موجود است)

مدل به صورت خودکار GPU را تشخیص می‌دهد. برای بررسی:

```bash
curl http://localhost:7001/api/v1/embeddings/info
```

اگر `"device": "cuda"` باشد، از GPU استفاده می‌شود.

### 2. Batch Processing

برای چند متن، حتماً batch استفاده کنید (سریع‌تر است):

```python
# ❌ کند
embeddings = [get_embedding(text) for text in texts]

# ✅ سریع
embeddings = get_batch_embeddings(texts)
```

### 3. Normalization

Embedding ها به صورت پیش‌فرض normalize شده‌اند (برای cosine similarity بهتر است).

---

## 🎯 مثال‌های کاربردی

### 1. جستجوی معنایی (Semantic Search)

```python
import numpy as np
from typing import List, Tuple

def semantic_search(
    query: str,
    documents: List[str],
    top_k: int = 5
) -> List[Tuple[int, float]]:
    """جستجوی معنایی در اسناد."""
    
    # Embedding query و documents
    all_texts = [query] + documents
    embeddings = get_batch_embeddings(all_texts)
    
    query_emb = embeddings[0]
    doc_embs = embeddings[1:]
    
    # محاسبه شباهت
    similarities = np.dot(doc_embs, query_emb)
    
    # مرتب‌سازی
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    results = [(idx, similarities[idx]) for idx in top_indices]
    return results


# مثال
documents = [
    "قانون کار ایران در سال 1369 تصویب شد",
    "قوانین مالیاتی مستقیم",
    "حقوق و دستمزد کارگران",
    "قانون تجارت الکترونیک"
]

results = semantic_search("قوانین کارگری", documents, top_k=2)

for idx, score in results:
    print(f"{score:.3f}: {documents[idx]}")
```

### 2. Clustering (خوشه‌بندی)

```python
from sklearn.cluster import KMeans

def cluster_documents(documents: List[str], n_clusters: int = 3):
    """خوشه‌بندی اسناد بر اساس محتوا."""
    
    # دریافت embeddings
    embeddings = get_batch_embeddings(documents)
    
    # خوشه‌بندی
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(embeddings)
    
    # گروه‌بندی
    clusters = {}
    for idx, label in enumerate(labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(documents[idx])
    
    return clusters


# مثال
docs = [
    "قانون کار",
    "قوانین استخدامی",
    "قوانین مالیاتی",
    "مالیات بر درآمد",
    "حقوق کارگران",
]

clusters = cluster_documents(docs, n_clusters=2)
for cluster_id, texts in clusters.items():
    print(f"\nCluster {cluster_id}:")
    for text in texts:
        print(f"  - {text}")
```

---

## 🔍 مقایسه با OpenAI

| ویژگی | Local (multilingual-e5-base) | OpenAI (text-embedding-3-large) |
|-------|------------------------------|----------------------------------|
| بُعد | 768 | 3072 |
| هزینه | رایگان | $0.13 / 1M tokens |
| سرعت | متوسط (CPU) / سریع (GPU) | سریع |
| آفلاین | ✅ بله | ❌ خیر |
| فارسی | ✅ عالی | ✅ عالی |
| حریم خصوصی | ✅ کامل | ❌ ارسال به سرور |

---

## 🛠 عیب‌یابی

### خطا: "Connection refused"
```bash
# چک کنید API در حال اجراست
curl http://localhost:7001/health
```

### خطا: "Model not loaded"
```bash
# Restart API
pkill -f uvicorn
cd /home/ahad/project/core
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 7001 --reload
```

### عملکرد کند
- از batch processing استفاده کنید
- اگر GPU دارید، PyTorch با CUDA نصب کنید
- مدل کوچک‌تر استفاده کنید (e5-small)

---

## 📚 منابع

- **مدل**: https://huggingface.co/intfloat/multilingual-e5-base
- **مقاله**: https://arxiv.org/abs/2402.05672
- **کتابخانه**: https://www.sbert.net

---

**🎉 آماده استفاده است!**
