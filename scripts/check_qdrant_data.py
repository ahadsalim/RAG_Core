#!/usr/bin/env python3
"""
اسکریپت بررسی داده‌های Qdrant
برای چک کردن وجود داده مرتبط با سوال کاربر
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.qdrant_service import QdrantService
from app.services.embedding_service import get_embedding_service


async def check_data():
    """بررسی داده‌های Qdrant"""
    
    qdrant = QdrantService()
    embedder = get_embedding_service()
    
    print("=" * 80)
    print("🔍 بررسی داده‌های Qdrant")
    print("=" * 80)
    
    # 1. Collection info
    try:
        info = await qdrant.get_collection_info()
        print(f"\n📊 Collection: {qdrant.collection_name}")
        print(f"   Points: {info['points_count']}")
        print(f"   Vectors: {info['vectors_count']}")
    except Exception as e:
        print(f"❌ خطا در دریافت اطلاعات collection: {e}")
        return
    
    # 2. جستجو برای "چلمنگان"
    print("\n" + "=" * 80)
    print("🔎 جستجو برای 'چلمنگان'")
    print("=" * 80)
    
    query_text = "قانون چلمنگان ماده ده"
    
    # Generate embedding
    print(f"\n📝 Query: {query_text}")
    query_embedding = embedder.encode_single(query_text)
    print(f"   Embedding dimension: {len(query_embedding)}")
    
    # Determine vector field
    dim = len(query_embedding)
    if dim <= 512:
        vector_field = "small"
    elif dim <= 768:
        vector_field = "medium"
    elif dim <= 1024:
        vector_field = "large"
    elif dim <= 1536:
        vector_field = "xlarge"
    else:
        vector_field = "default"
    
    print(f"   Vector field: {vector_field}")
    
    # Search with different thresholds
    thresholds = [0.5, 0.6, 0.7, 0.8]
    
    for threshold in thresholds:
        print(f"\n--- Threshold: {threshold} ---")
        
        try:
            results = await qdrant.search(
                query_vector=query_embedding.tolist(),
                limit=10,
                score_threshold=threshold,
                vector_field=vector_field
            )
            
            print(f"✅ نتایج یافت شده: {len(results)}")
            
            for i, result in enumerate(results[:5], 1):
                print(f"\n{i}. Score: {result['score']:.4f}")
                print(f"   Text: {result['text'][:200]}...")
                metadata = result.get('metadata', {})
                print(f"   Document: {metadata.get('work_title', 'N/A')}")
                print(f"   Unit: {metadata.get('unit_number', 'N/A')}")
                
        except Exception as e:
            print(f"❌ خطا در جستجو: {e}")
    
    # 3. جستجو با کلمات کلیدی مختلف
    print("\n" + "=" * 80)
    print("🔎 جستجو با کلمات کلیدی مختلف")
    print("=" * 80)
    
    queries = [
        "چلمنگان",
        "قانون چلمنگان",
        "ماده ده",
        "ماده 10",
        "قانون تأمین اجتماعی",
        "قانون اساسی",
    ]
    
    for query in queries:
        print(f"\n--- Query: '{query}' ---")
        query_emb = embedder.encode_single(query)
        
        try:
            results = await qdrant.search(
                query_vector=query_emb.tolist(),
                limit=3,
                score_threshold=0.5,
                vector_field=vector_field
            )
            
            print(f"نتایج: {len(results)}")
            for i, result in enumerate(results, 1):
                metadata = result.get('metadata', {})
                print(f"  {i}. [{result['score']:.3f}] {metadata.get('work_title', 'N/A')} - {metadata.get('unit_number', 'N/A')}")
                
        except Exception as e:
            print(f"❌ خطا: {e}")
    
    print("\n" + "=" * 80)
    print("✅ بررسی تمام شد")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(check_data())
