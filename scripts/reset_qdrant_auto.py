#!/usr/bin/env python3
"""
Auto Reset Qdrant Collection (Non-interactive)
===============================================
This script automatically deletes and recreates the Qdrant collection
without requiring user confirmation. Use with caution!

Usage:
    python scripts/reset_qdrant_auto.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.qdrant_service import QdrantService
from app.config.settings import settings
from qdrant_client.models import Distance, VectorParams, OptimizersConfigDiff
import structlog

logger = structlog.get_logger()


def main():
    """Delete and recreate Qdrant collection automatically."""
    print("=" * 70)
    print("Qdrant Collection Auto Reset")
    print("=" * 70)
    print()
    
    qdrant = QdrantService()
    
    try:
        # Get current collection info
        print(f"📊 Checking current collection: {settings.qdrant_collection}")
        try:
            info = qdrant.client.get_collection(settings.qdrant_collection)
            print(f"   Points: {info.points_count}")
            print(f"   Vectors: {info.vectors_count}")
            print(f"   Status: {info.status}")
        except Exception as e:
            print(f"   Collection does not exist: {e}")
        
        print()
        print("🗑️  Deleting collection...")
        qdrant.client.delete_collection(collection_name=settings.qdrant_collection)
        print("✅ Deleted!")
        
        print()
        print("🔨 Creating new collection...")
        qdrant.client.create_collection(
            collection_name=settings.qdrant_collection,
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
        print("✅ Created!")
        
        print()
        print("📊 New collection info:")
        info = qdrant.client.get_collection(settings.qdrant_collection)
        print(f"   Status: {info.status}")
        print(f"   Points: {info.points_count}")
        
        print()
        print("=" * 70)
        print("✅ SUCCESS! Qdrant ready for 1024-dim embeddings (e5-large)")
        print("=" * 70)
        print()
        print("Next: Ingest system can now sync data with e5-large embeddings")
        print()
        
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Error: {e}")
        print("=" * 70)
        logger.error(f"Reset failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
