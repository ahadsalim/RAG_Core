#!/usr/bin/env python3
"""
Reset Qdrant Collection for Embedding Model Change
===================================================
This script deletes and recreates the Qdrant collection when the embedding
model changes (e.g., from e5-base (768d) to e5-large (1024d)).

Usage:
    python scripts/reset_qdrant_collection.py

IMPORTANT: This will delete ALL vectors in Qdrant!
Make sure the ingest system is ready to re-sync all data.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.qdrant_service import QdrantService
from app.config.settings import settings
import structlog

logger = structlog.get_logger()


def main():
    """Delete and recreate Qdrant collection."""
    print("=" * 70)
    print("Qdrant Collection Reset Script")
    print("=" * 70)
    print()
    print("⚠️  WARNING: This will DELETE ALL vectors in Qdrant!")
    print(f"   Collection: {settings.qdrant_collection}")
    print(f"   Host: {settings.qdrant_host}:{settings.qdrant_port}")
    print()
    
    # Confirm action
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Operation cancelled.")
        return
    
    print()
    print("Initializing Qdrant service...")
    qdrant = QdrantService()
    
    try:
        # Get current collection info
        print(f"📊 Checking current collection status...")
        try:
            info = qdrant.client.get_collection(settings.qdrant_collection)
            print(f"   Current points count: {info.points_count}")
            print(f"   Current vectors count: {info.vectors_count}")
            print(f"   Current status: {info.status}")
        except Exception as e:
            print(f"   Collection does not exist or error: {e}")
        
        print()
        print("🗑️  Deleting collection...")
        qdrant.client.delete_collection(collection_name=settings.qdrant_collection)
        print("✅ Collection deleted successfully!")
        
        print()
        print("🔨 Creating new collection with updated configuration...")
        print("   Supported dimensions:")
        print("      - small: 512")
        print("      - medium: 768")
        print("      - large: 1024  ← e5-large")
        print("      - xlarge: 1536")
        print("      - default: 3072")
        
        # Create collection with updated config
        from qdrant_client.models import Distance, VectorParams, OptimizersConfigDiff
        
        qdrant.client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config={
                "default": VectorParams(
                    size=3072,  # For large embedding models (e.g., text-embedding-3-large)
                    distance=Distance.COSINE,
                ),
                "small": VectorParams(
                    size=512,  # Smaller models
                    distance=Distance.COSINE,
                ),
                "medium": VectorParams(
                    size=768,  # BERT-based models, e5-base
                    distance=Distance.COSINE,
                ),
                "large": VectorParams(
                    size=1024,  # e5-large, bge-m3
                    distance=Distance.COSINE,
                ),
                "xlarge": VectorParams(
                    size=1536,  # OpenAI ada-002, text-embedding-3-small
                    distance=Distance.COSINE,
                ),
            },
            optimizers_config=OptimizersConfigDiff(
                indexing_threshold=20000,
                memmap_threshold=50000,
            ),
        )
        print("✅ Collection created successfully!")
        
        print()
        print("📊 New collection info:")
        info = qdrant.client.get_collection(settings.qdrant_collection)
        print(f"   Status: {info.status}")
        print(f"   Points count: {info.points_count}")
        
        print()
        print("=" * 70)
        print("✅ Qdrant collection reset completed successfully!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Make sure the ingest system is configured with e5-large model")
        print("2. Re-embed all chunks in the ingest system")
        print("3. Sync all embeddings to Core using: POST /api/v1/sync/embeddings")
        print()
        
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Error: {e}")
        print("=" * 70)
        logger.error(f"Failed to reset collection: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
