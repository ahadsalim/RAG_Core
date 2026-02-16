#!/usr/bin/env python3
"""
Reset Qdrant Collection - Unified Script
=========================================
This script manages the Qdrant collection for the RAG Core system.
Use this when:
- Changing embedding model dimensions
- Clearing all vectors for fresh resync
- Troubleshooting Qdrant issues

Usage:
    python tools/reset_qdrant_collection.py           # Interactive mode
    python tools/reset_qdrant_collection.py --force   # Non-interactive (use with caution)
    python tools/reset_qdrant_collection.py --info    # Show collection info only

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


def show_info():
    """Show current collection info."""
    print("=" * 70)
    print("📊 Qdrant Collection Info")
    print("=" * 70)
    print()
    print(f"   Collection: {settings.qdrant_collection}")
    print(f"   Host: {settings.qdrant_host}:{settings.qdrant_port}")
    print()
    
    try:
        qdrant = QdrantService()
        info = qdrant.client.get_collection(settings.qdrant_collection)
        print(f"   Points: {info.points_count}")
        print(f"   Vectors: {info.vectors_count}")
        print(f"   Status: {info.status}")
        print()
        print("   Vector Configs:")
        for name, config in info.config.params.vectors.items():
            print(f"      {name}: {config.size}d")
    except Exception as e:
        print(f"   Collection not found: {e}")
    print()


def create_collection(qdrant):
    """Create collection with multi-dimensional support."""
    from qdrant_client.models import Distance, VectorParams, OptimizersConfigDiff
    
    qdrant.client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config={
            "default": VectorParams(
                size=3072,  # For large embedding models
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


def main():
    """Delete and recreate Qdrant collection."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Reset Qdrant Collection')
    parser.add_argument('--force', '-f', action='store_true', 
                        help='Skip confirmation prompt')
    parser.add_argument('--info', '-i', action='store_true',
                        help='Show collection info only')
    args = parser.parse_args()
    
    # Info only mode
    if args.info:
        show_info()
        return
    
    print("=" * 70)
    print("Qdrant Collection Reset Script")
    print("=" * 70)
    print()
    print("⚠️  WARNING: This will DELETE ALL vectors in Qdrant!")
    print(f"   Collection: {settings.qdrant_collection}")
    print(f"   Host: {settings.qdrant_host}:{settings.qdrant_port}")
    print()
    
    # Confirm action unless --force
    if not args.force:
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Operation cancelled.")
            return
    else:
        print("🚨 Force mode enabled - skipping confirmation")
    
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
        print("🛠️  Creating new collection with multi-dimensional support...")
        print("   Supported dimensions:")
        print("      - small: 512")
        print("      - medium: 768")
        print("      - large: 1024  ← e5-large (default)")
        print("      - xlarge: 1536")
        print("      - default: 3072")
        
        create_collection(qdrant)
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
