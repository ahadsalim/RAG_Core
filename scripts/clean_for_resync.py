#!/usr/bin/env python3
"""
Clean all data for fresh resync from Ingest
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.qdrant_service import QdrantService
from qdrant_client.models import Distance, VectorParams, OptimizersConfigDiff
from app.config.settings import settings


def main():
    print("=" * 70)
    print("🧹 Cleaning System for Fresh Resync")
    print("=" * 70)
    print()
    
    qdrant = QdrantService()
    
    # 1. Check current state
    print("1️⃣  Current State:")
    try:
        info = qdrant.client.get_collection(qdrant.collection_name)
        print(f"   Collection: {qdrant.collection_name}")
        print(f"   Points: {info.points_count}")
        print(f"   Status: {info.status}")
    except Exception as e:
        print(f"   Collection not found or error: {e}")
    print()
    
    # 2. Delete collection
    print("2️⃣  Deleting Collection...")
    try:
        qdrant.client.delete_collection(collection_name=qdrant.collection_name)
        print("   ✅ Collection deleted!")
    except Exception as e:
        print(f"   ⚠️  Error deleting: {e}")
    print()
    
    # 3. Recreate collection with fresh config
    print("3️⃣  Creating Fresh Collection...")
    try:
        qdrant.client.create_collection(
            collection_name=qdrant.collection_name,
            vectors_config={
                "default": VectorParams(
                    size=3072,
                    distance=Distance.COSINE,
                ),
                "small": VectorParams(
                    size=512,
                    distance=Distance.COSINE,
                ),
                "medium": VectorParams(
                    size=768,
                    distance=Distance.COSINE,
                ),
                "large": VectorParams(
                    size=1024,  # e5-large
                    distance=Distance.COSINE,
                ),
                "xlarge": VectorParams(
                    size=1536,
                    distance=Distance.COSINE,
                ),
            },
            optimizers_config=OptimizersConfigDiff(
                indexing_threshold=20000,
                memmap_threshold=50000,
            ),
        )
        print("   ✅ Collection created!")
    except Exception as e:
        print(f"   ❌ Error creating: {e}")
        sys.exit(1)
    print()
    
    # 4. Verify new collection
    print("4️⃣  Verifying New Collection:")
    info = qdrant.client.get_collection(qdrant.collection_name)
    print(f"   Collection: {qdrant.collection_name}")
    print(f"   Points: {info.points_count}")
    print(f"   Status: {info.status}")
    print(f"   Vectors Config:")
    for name, config in info.config.params.vectors.items():
        print(f"      {name}: {config.size}d")
    print()
    
    print("=" * 70)
    print("✅ System Ready for Fresh Resync!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Ingest system can now sync all 4304 vectors")
    print("2. Use: POST /api/v1/sync/embeddings")
    print("3. System will auto-detect dimension and use 'large' field")
    print()


if __name__ == "__main__":
    main()
