#!/usr/bin/env python3
"""
Quick verification after sync completes
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.qdrant_service import QdrantService


def main():
    qdrant = QdrantService()
    
    print("=" * 70)
    print("✅ Quick Sync Verification")
    print("=" * 70)
    print()
    
    # Get collection info
    info = qdrant.client.get_collection(qdrant.collection_name)
    
    expected = 4304
    actual = info.points_count
    diff = actual - expected
    
    print(f"Expected: {expected}")
    print(f"Actual:   {actual}")
    print(f"Diff:     {diff:+d}")
    print()
    
    # Check status
    if diff == 0:
        print("✅ PERFECT MATCH!")
    elif abs(diff) <= 5:
        print("✅ ACCEPTABLE (within ±5)")
    else:
        print("⚠️  SIGNIFICANT DIFFERENCE")
    
    print()
    print(f"Collection Status: {info.status}")
    
    # Sample check
    print()
    print("Checking sample data...")
    samples = qdrant.client.scroll(
        collection_name=qdrant.collection_name,
        limit=10,
        with_payload=True,
        with_vectors=True
    )[0]
    
    if samples:
        # Check vector field
        vector_fields = set()
        for point in samples:
            if hasattr(point, 'vector') and point.vector:
                vector_fields.update(point.vector.keys())
        
        print(f"Vector fields used: {', '.join(vector_fields)}")
        
        # Check first point
        first = samples[0]
        if hasattr(first, 'vector') and first.vector:
            for field, vec in first.vector.items():
                print(f"Sample dimension: {len(vec)}d ({field})")
                break
        
        # Check metadata
        if first.payload and 'metadata' in first.payload:
            meta = first.payload['metadata']
            if isinstance(meta, dict):
                if 'embedding_model' in meta:
                    print(f"Embedding model: {meta['embedding_model']}")
                if 'embedding_dimension' in meta:
                    print(f"Embedding dim: {meta['embedding_dimension']}")
    
    print()
    print("=" * 70)
    
    if diff == 0:
        print("🎉 Perfect sync! All 4304 vectors received!")
    else:
        print(f"Sync complete with {actual} vectors")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
