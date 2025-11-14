# 🏗️ ساختار بهینه Qdrant برای سیستم Core

## 📊 تحلیل ساختار داده Ingest

### 1️⃣ **Models اصلی در Ingest**

#### **InstrumentWork** (FRBR Work)
```python
- id (UUID)
- title_official (عنوان رسمی)
- doc_type (نوع سند: LAW, REGULATION, DECREE, ...)
- jurisdiction (حوزه قضایی)
- authority (مرجع صادرکننده)
- urn_lex (شناسه URN LEX)
- primary_language (زبان اصلی)
- subject_summary (خلاصه موضوع)
```

#### **InstrumentExpression** (FRBR Expression)
```python
- id (UUID)
- work (FK to InstrumentWork)
- language (زبان)
- consolidation_level (سطح تلفیق)
- expression_date (تاریخ نسخه)
- eli_uri_expr (ELI URI)
```

#### **InstrumentManifestation** (FRBR Manifestation)
```python
- id (UUID)
- expr (FK to InstrumentExpression)
- publication_date (تاریخ انتشار)
- official_gazette_name (نام روزنامه رسمی)
- gazette_issue_no (شماره نامه)
- page_start (صفحه شروع)
- source_url (URL منبع)
- in_force_from (اجرا از تاریخ)
- in_force_to (اجرا تا تاریخ)
- repeal_status (وضعیت: in_force / repealed)
```

#### **LegalUnit** (واحد قانونی - MPTT)
```python
- id (UUID)
- work (FK to InstrumentWork)
- expr (FK to InstrumentExpression)
- manifestation (FK to InstrumentManifestation)
- parent (TreeForeignKey - سلسله مراتبی)
- unit_type (نوع: PART, CHAPTER, SECTION, ARTICLE, CLAUSE, ...)
- number (شماره)
- order_index (ترتیب)
- path_label (مسیر کامل: "قانون کار > فصل اول > ماده 1")
- content (محتوای متنی)
- eli_fragment (ELI Fragment)
- xml_id (XML ID)
- vocabulary_terms (M2M: برچسب‌ها)
- valid_from (تاریخ شروع اعتبار)
- valid_to (تاریخ پایان اعتبار)
```

#### **Chunk** (تکه متن برای RAG)
```python
- id (UUID)
- expr (FK to InstrumentExpression)
- unit (FK to LegalUnit)
- chunk_text (متن تکه)
- token_count (تعداد توکن)
- overlap_prev (همپوشانی با قبلی)
- citation_payload_json (JSONField: اطلاعات ارجاع)
- hash (SHA-256)
```

#### **Embedding** (بردار)
```python
- id (UUID)
- content_type (FK: نوع محتوا - Chunk/QAEntry/...)
- object_id (UUID: شناسه آبجکت)
- model_id (شناسه مدل: "intfloat/multilingual-e5-base")
- model_version (نسخه مدل)
- model_name (نام مدل - legacy)
- vector (VectorField: بردار pgvector)
- dim (بعد واقعی بردار: 768)
- dimension (بعد - legacy: 512)
- text_content (محتوای متنی)
- synced_to_core (Boolean)
- synced_at (DateTime)
- sync_error (Text)
```

#### **QAEntry** (پرسش و پاسخ)
```python
- id (UUID)
- question (سؤال)
- answer (پاسخ)
- status (DRAFT, APPROVED, REJECTED)
- tags (M2M: برچسب‌ها)
- source_unit (FK to LegalUnit)
- source_work (FK to InstrumentWork)
- canonical_question (نسخه نرمال شده)
```

---

## 🎯 داده‌هایی که به Qdrant منتقل می‌شوند

### از Sync Task (`ingest/tasks/core_sync.py`):

```python
{
    'id': str(embedding.id),              # UUID embedding
    'vector': [0.1, 0.2, ...],           # بردار 768 بعدی
    'text': embedding.text_content,       # متن کامل
    'document_id': str(embedding.object_id),  # UUID آبجکت اصلی
    'metadata': {
        'content_type': 'chunk' or 'qaentry',
        'model_id': 'intfloat/multilingual-e5-base',
        'model_name': 'multilingual-e5-base',
        'dimension': 768,
        'created_at': '2025-11-02T...',
    }
}
```

---

## ❌ **مشکل: اطلاعات ناکافی!**

**این ساختار فعلی مشکل دارد:**

1. ❌ فقط `text_content` منتقل می‌شود (بدون context)
2. ❌ متادیتای کامل از LegalUnit منتقل نمی‌شود
3. ❌ ساختار سلسله‌مراتبی (path_label) موجود نیست
4. ❌ اطلاعات Work/Expression/Manifestation موجود نیست
5. ❌ تاریخ‌های اعتبار (valid_from/valid_to) موجود نیست
6. ❌ اطلاعات قانونی (مرجع، نوع سند، ...) موجود نیست

---

## ✅ **ساختار بهینه پیشنهادی برای Qdrant**

### **مدل 1: Rich Metadata (توصیه شده)**

این مدل تمام اطلاعات لازم برای RAG پیشرفته را ذخیره می‌کند:

```python
{
    # شناسایی اصلی
    "id": "uuid-string",                    # UUID embedding
    "chunk_id": "uuid-string",              # UUID chunk اصلی
    "unit_id": "uuid-string",               # UUID legal unit
    
    # بردار
    "vector": {
        "medium": [768 float values]        # بردار embedding
    },
    
    # محتوای متنی
    "text": "متن کامل تکه...",             # متن اصلی
    "text_normalized": "متن نرمال شده...",  # متن تمیز شده
    
    # ساختار سلسله‌مراتبی
    "path_label": "قانون کار > فصل اول > ماده 1",
    "unit_type": "ARTICLE",                 # نوع واحد
    "unit_number": "1",                     # شماره
    "parent_path": "قانون کار > فصل اول",  # مسیر والد
    
    # اطلاعات سند (FRBR Work)
    "work_id": "uuid-string",
    "work_title": "قانون کار جمهوری اسلامی ایران",
    "doc_type": "LAW",                      # نوع سند
    "urn_lex": "ir:majlis:law:1990-06-01:123",
    
    # اطلاعات نسخه (FRBR Expression)
    "expression_id": "uuid-string",
    "language": "fa",                       # زبان
    "consolidation_level": "BASE",          # سطح تلفیق
    "expression_date": "2020-01-01",
    
    # اطلاعات انتشار (FRBR Manifestation)
    "manifestation_id": "uuid-string",
    "publication_date": "2020-06-15",
    "official_gazette": "روزنامه رسمی",
    "gazette_issue_no": "12345",
    "source_url": "https://...",
    
    # اطلاعات حقوقی
    "jurisdiction": "ایران",                # حوزه قضایی
    "authority": "مجلس شورای اسلامی",      # مرجع
    "primary_language": "fa",
    
    # اعتبار زمانی
    "valid_from": "2020-07-01",            # تاریخ شروع اعتبار
    "valid_to": null,                      # تاریخ پایان (null = همیشه)
    "is_active": true,                     # فعال بودن
    "in_force_from": "2020-07-01",         # تاریخ اجرا
    "in_force_to": null,
    "repeal_status": "in_force",           # وضعیت: in_force / repealed
    
    # متادیتای تکنیکال
    "chunk_index": 0,                      # شماره تکه
    "token_count": 256,                    # تعداد توکن
    "overlap_prev": 50,                    # همپوشانی
    "chunk_hash": "sha256-hash",
    
    # متادیتای embedding
    "embedding_model": "intfloat/multilingual-e5-base",
    "embedding_dimension": 768,
    "embedding_created_at": "2025-11-02T...",
    
    # برچسب‌ها و دسته‌بندی
    "tags": ["کار", "استخدام", "حقوق کارگران"],
    "vocabulary_terms": [
        {"term": "قانون کار", "weight": 10},
        {"term": "استخدام", "weight": 8}
    ],
    
    # ارجاعات
    "citations": [
        {
            "from_unit": "ماده 1",
            "to_unit": "ماده 5",
            "type": "direct"
        }
    ],
    
    # متادیتای سیستمی
    "source": "ingest",                    # منبع داده
    "content_type": "chunk",               # نوع: chunk / qa_entry
    "created_at": "2025-11-02T...",
    "updated_at": "2025-11-02T...",
    "version": 1                           # نسخه
}
```

---

### **مدل 2: Minimal (برای سرعت بالا)**

اگر فقط سرعت مهم است:

```python
{
    "id": "uuid",
    "vector": {"medium": [768 floats]},
    "text": "متن کامل...",
    
    # حداقل metadata
    "work_title": "قانون کار",
    "path_label": "قانون کار > فصل اول > ماده 1",
    "doc_type": "LAW",
    "language": "fa",
    "is_active": true,
    "created_at": "2025-11-02T..."
}
```

---

### **مدل 3: Hybrid (توصیه برای استارت)**

تعادل بین اطلاعات و سرعت:

```python
{
    # شناسایی
    "id": "uuid",
    "chunk_id": "uuid",
    "unit_id": "uuid",
    
    # بردار
    "vector": {"medium": [768 floats]},
    
    # محتوا
    "text": "متن کامل...",
    "path_label": "قانون کار > فصل اول > ماده 1",
    "unit_type": "ARTICLE",
    "unit_number": "1",
    
    # اطلاعات سند
    "work_id": "uuid",
    "work_title": "قانون کار جمهوری اسلامی ایران",
    "doc_type": "LAW",
    "language": "fa",
    
    # اطلاعات حقوقی
    "jurisdiction": "ایران",
    "authority": "مجلس شورای اسلامی",
    "publication_date": "2020-06-15",
    
    # اعتبار
    "valid_from": "2020-07-01",
    "valid_to": null,
    "is_active": true,
    "repeal_status": "in_force",
    
    # متادیتا
    "embedding_model": "intfloat/multilingual-e5-base",
    "embedding_dimension": 768,
    "source": "ingest",
    "content_type": "chunk",
    "created_at": "2025-11-02T..."
}
```

---

## 🔧 پیاده‌سازی در Core

### 1️⃣ **تغییر Sync Service در Ingest**

فایل: `/home/ahad/project/ingest/ingest/tasks/core_sync.py`

```python
@shared_task(bind=True, max_retries=3)
def auto_sync_to_core(self, batch_size=100):
    """Sync embeddings با metadata کامل."""
    
    from ingest.apps.embeddings.models import Embedding
    from ingest.apps.documents.models import Chunk, LegalUnit
    from django.contrib.contenttypes.models import ContentType
    
    embeddings = Embedding.objects.filter(
        synced_to_core=False
    ).select_related(
        'content_type'
    )[:batch_size]
    
    data = []
    for emb in embeddings:
        # Get the source object (Chunk or QAEntry)
        source_obj = emb.content_object
        
        if isinstance(source_obj, Chunk):
            unit = source_obj.unit
            expr = source_obj.expr
            work = expr.work if expr else None
            manifestation = unit.manifestation
            
            payload = {
                'id': str(emb.id),
                'chunk_id': str(source_obj.id),
                'unit_id': str(unit.id),
                'vector': emb.vector.tolist() if hasattr(emb.vector, 'tolist') else list(emb.vector),
                'text': emb.text_content,
                
                # Path and structure
                'path_label': unit.path_label,
                'unit_type': unit.unit_type,
                'unit_number': unit.number,
                
                # Work info
                'work_id': str(work.id) if work else None,
                'work_title': work.title_official if work else '',
                'doc_type': work.doc_type if work else '',
                'urn_lex': work.urn_lex if work else '',
                
                # Expression info
                'expression_id': str(expr.id) if expr else None,
                'language': expr.language.code if expr and expr.language else 'fa',
                'consolidation_level': expr.consolidation_level if expr else '',
                'expression_date': expr.expression_date.isoformat() if expr and expr.expression_date else None,
                
                # Manifestation info
                'manifestation_id': str(manifestation.id) if manifestation else None,
                'publication_date': manifestation.publication_date.isoformat() if manifestation else None,
                'official_gazette': manifestation.official_gazette_name if manifestation else '',
                'gazette_issue_no': manifestation.gazette_issue_no if manifestation else '',
                'source_url': manifestation.source_url if manifestation else '',
                
                # Legal info
                'jurisdiction': work.jurisdiction.name if work and work.jurisdiction else '',
                'authority': work.authority.name if work and work.authority else '',
                
                # Validity
                'valid_from': unit.valid_from.isoformat() if unit.valid_from else None,
                'valid_to': unit.valid_to.isoformat() if unit.valid_to else None,
                'is_active': unit.is_active,
                'in_force_from': manifestation.in_force_from.isoformat() if manifestation and manifestation.in_force_from else None,
                'in_force_to': manifestation.in_force_to.isoformat() if manifestation and manifestation.in_force_to else None,
                'repeal_status': manifestation.repeal_status if manifestation else 'in_force',
                
                # Technical metadata
                'chunk_index': 0,  # TODO: calculate from chunk position
                'token_count': source_obj.token_count,
                'overlap_prev': source_obj.overlap_prev,
                'chunk_hash': source_obj.hash,
                
                # Embedding metadata
                'embedding_model': emb.model_id,
                'embedding_dimension': emb.dim,
                'embedding_created_at': emb.created_at.isoformat(),
                
                # System metadata
                'source': 'ingest',
                'content_type': 'chunk',
                'created_at': source_obj.created_at.isoformat(),
                'updated_at': source_obj.updated_at.isoformat(),
            }
            
            # Add tags if available
            if unit.vocabulary_terms.exists():
                payload['tags'] = [term.term for term in unit.vocabulary_terms.all()]
                payload['vocabulary_terms'] = [
                    {'term': vt.vocabulary_term.term, 'weight': vt.weight}
                    for vt in unit.unit_vocabulary_terms.select_related('vocabulary_term')
                ]
            
            data.append(payload)
    
    # Send to Core...
    # (rest of the code remains same)
```

---

### 2️⃣ **تغییر Qdrant Service در Core**

فایل: `/home/ahad/project/core/app/services/qdrant_service.py`

```python
async def upsert_embeddings(
    self,
    embeddings: List[Dict[str, Any]],
    vector_field: str = "medium"
) -> int:
    """Upsert embeddings با metadata کامل."""
    
    points = []
    for emb in embeddings:
        point_id = emb.get("id", str(uuid.uuid4()))
        if isinstance(point_id, str):
            point_id = int(hashlib.md5(point_id.encode()).hexdigest()[:16], 16)
        
        # Rich payload
        payload = {
            # IDs
            "chunk_id": emb.get("chunk_id"),
            "unit_id": emb.get("unit_id"),
            "work_id": emb.get("work_id"),
            "expression_id": emb.get("expression_id"),
            "manifestation_id": emb.get("manifestation_id"),
            
            # Content
            "text": emb["text"],
            "path_label": emb.get("path_label", ""),
            "unit_type": emb.get("unit_type", ""),
            "unit_number": emb.get("unit_number", ""),
            
            # Document info
            "work_title": emb.get("work_title", ""),
            "doc_type": emb.get("doc_type", ""),
            "urn_lex": emb.get("urn_lex", ""),
            "language": emb.get("language", "fa"),
            "consolidation_level": emb.get("consolidation_level", ""),
            "expression_date": emb.get("expression_date"),
            
            # Publication
            "publication_date": emb.get("publication_date"),
            "official_gazette": emb.get("official_gazette", ""),
            "gazette_issue_no": emb.get("gazette_issue_no", ""),
            "source_url": emb.get("source_url", ""),
            
            # Legal
            "jurisdiction": emb.get("jurisdiction", ""),
            "authority": emb.get("authority", ""),
            
            # Validity
            "valid_from": emb.get("valid_from"),
            "valid_to": emb.get("valid_to"),
            "is_active": emb.get("is_active", True),
            "in_force_from": emb.get("in_force_from"),
            "in_force_to": emb.get("in_force_to"),
            "repeal_status": emb.get("repeal_status", "in_force"),
            
            # Technical
            "chunk_index": emb.get("chunk_index", 0),
            "token_count": emb.get("token_count", 0),
            "overlap_prev": emb.get("overlap_prev", 0),
            "chunk_hash": emb.get("chunk_hash", ""),
            
            # Embedding
            "embedding_model": emb.get("embedding_model", ""),
            "embedding_dimension": emb.get("embedding_dimension", 768),
            "embedding_created_at": emb.get("embedding_created_at"),
            
            # Tags
            "tags": emb.get("tags", []),
            "vocabulary_terms": emb.get("vocabulary_terms", []),
            
            # System
            "source": emb.get("source", "ingest"),
            "content_type": emb.get("content_type", "chunk"),
            "created_at": emb.get("created_at"),
            "updated_at": emb.get("updated_at"),
        }
        
        point = PointStruct(
            id=point_id,
            vector={vector_field: emb["vector"]},
            payload=payload
        )
        points.append(point)
    
    # Upsert in batches...
```

---

### 3️⃣ **استفاده در RAG Pipeline**

با این metadata غنی، می‌توانید:

```python
# فیلتر پیشرفته
results = await self.qdrant.search(
    query_vector=query_embedding,
    limit=20,
    filters={
        "must": [
            {"key": "is_active", "match": {"value": True}},
            {"key": "language", "match": {"value": "fa"}},
            {"key": "repeal_status", "match": {"value": "in_force"}},
        ],
        "should": [
            {"key": "doc_type", "match": {"value": "LAW"}},
            {"key": "doc_type", "match": {"value": "REGULATION"}},
        ],
        "must_not": [
            {"key": "valid_to", "range": {"lt": "2025-11-02"}},  # Expired
        ]
    }
)

# استفاده از metadata در پاسخ
for chunk in results:
    print(f"منبع: {chunk['work_title']}")
    print(f"مسیر: {chunk['path_label']}")
    print(f"تاریخ انتشار: {chunk['publication_date']}")
    print(f"مرجع: {chunk['authority']}")
    print(f"وضعیت: {chunk['repeal_status']}")
```

---

## 📊 مقایسه مدل‌ها

| ویژگی | Minimal | Hybrid | Rich |
|-------|---------|--------|------|
| **حجم هر Point** | ~2 KB | ~5 KB | ~10 KB |
| **سرعت جستجو** | بسیار سریع | سریع | متوسط |
| **قابلیت فیلتر** | محدود | خوب | عالی |
| **Context در پاسخ** | ضعیف | خوب | عالی |
| **نگهداری** | ساده | متوسط | پیچیده |
| **توصیه برای** | MVP | Production | Enterprise |

---

## 🎯 توصیه نهایی

**برای شروع: مدل Hybrid**

چرا؟
- ✅ اطلاعات کافی برای RAG پیشرفته
- ✅ سرعت قابل قبول
- ✅ قابلیت فیلتر خوب
- ✅ نمایش منابع معتبر
- ✅ پشتیبانی از temporal queries (valid_from/valid_to)

**بعداً**: اگر نیاز به قابلیت‌های پیشرفته‌تر بود، به Rich ارتقا دهید.

---

## 📁 فایل‌های نیاز به تغییر

1. `/home/ahad/project/ingest/ingest/tasks/core_sync.py` - اضافه کردن metadata کامل
2. `/home/ahad/project/core/app/services/qdrant_service.py` - پذیرش metadata کامل
3. `/home/ahad/project/core/app/rag/pipeline.py` - استفاده از metadata در فیلترها
4. `/home/ahad/project/core/app/api/v1/endpoints/sync.py` - validation metadata

---

**🎉 با این ساختار، سیستم RAG شما قدرتمند و انعطاف‌پذیر خواهد بود!**
