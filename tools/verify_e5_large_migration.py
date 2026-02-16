#!/usr/bin/env python3
"""
Verify E5-Large Migration Completeness
Check all configurations and code for proper e5-large setup
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import settings
from app.services.qdrant_service import QdrantService
from app.services.embedding_service import get_embedding_service


def main():
    print("=" * 80)
    print("🔍 E5-LARGE MIGRATION VERIFICATION")
    print("=" * 80)
    print()
    
    issues = []
    warnings = []
    
    # 1. Check Environment Variables
    print("1️⃣  Environment Variables")
    print("-" * 80)
    print(f"   EMBEDDING_MODEL: {settings.embedding_model}")
    print(f"   EMBEDDING_DIM: {settings.embedding_dim}")
    print(f"   EMBEDDING_API_KEY: {'Set' if settings.embedding_api_key else 'Empty (Local Mode)'}")
    print(f"   EMBEDDING_BASE_URL: {settings.embedding_base_url or 'Empty (Local Mode)'}")
    print()
    
    # Verify model
    if "e5-large" not in settings.embedding_model:
        issues.append(f"EMBEDDING_MODEL is not e5-large: {settings.embedding_model}")
    else:
        print("   ✅ Model is e5-large")
    
    # Verify dimension
    if settings.embedding_dim != 1024:
        issues.append(f"EMBEDDING_DIM is not 1024: {settings.embedding_dim}")
    else:
        print("   ✅ Dimension is 1024")
    
    print()
    
    # 2. Check Embedding Service
    print("2️⃣  Embedding Service")
    print("-" * 80)
    try:
        embedding_service = get_embedding_service()
        print(f"   Mode: {embedding_service.get_mode()}")
        print(f"   Model: {embedding_service.get_model_name()}")
        print(f"   Dimension: {embedding_service.get_embedding_dimension()}")
        
        if embedding_service.get_embedding_dimension() != 1024:
            issues.append(f"Embedding service dimension mismatch: {embedding_service.get_embedding_dimension()}")
        else:
            print("   ✅ Service dimension is 1024")
        
        if "e5-large" not in embedding_service.get_model_name():
            warnings.append(f"Embedding service model name doesn't contain 'e5-large': {embedding_service.get_model_name()}")
        else:
            print("   ✅ Service model is e5-large")
        
    except Exception as e:
        issues.append(f"Failed to initialize embedding service: {e}")
    
    print()
    
    # 3. Check Qdrant Configuration
    print("3️⃣  Qdrant Configuration")
    print("-" * 80)
    try:
        qdrant = QdrantService()
        info = qdrant.client.get_collection(qdrant.collection_name)
        
        print(f"   Collection: {qdrant.collection_name}")
        print(f"   Status: {info.status}")
        print(f"   Points: {info.points_count}")
        print()
        
        print("   Vector Fields:")
        vectors = info.config.params.vectors
        for name, config in vectors.items():
            print(f"      {name:10s}: {config.size}d")
        
        # Check if 'large' field exists and is 1024
        if 'large' not in vectors:
            issues.append("Qdrant collection missing 'large' vector field")
        elif vectors['large'].size != 1024:
            issues.append(f"Qdrant 'large' field has wrong dimension: {vectors['large'].size}")
        else:
            print()
            print("   ✅ Qdrant 'large' field configured for 1024d")
        
    except Exception as e:
        issues.append(f"Failed to check Qdrant: {e}")
    
    print()
    
    # 4. Check Sample Data (if any exists)
    print("4️⃣  Sample Data Check")
    print("-" * 80)
    try:
        qdrant = QdrantService()
        info = qdrant.client.get_collection(qdrant.collection_name)
        
        if info.points_count > 0:
            samples = qdrant.client.scroll(
                collection_name=qdrant.collection_name,
                limit=10,
                with_payload=True,
                with_vectors=True
            )[0]
            
            if samples:
                # Check vector fields used
                vector_fields_used = set()
                for point in samples:
                    if hasattr(point, 'vector') and point.vector:
                        vector_fields_used.update(point.vector.keys())
                
                print(f"   Sample size: {len(samples)} points")
                print(f"   Vector fields in use: {', '.join(vector_fields_used)}")
                
                # Check if using 'large' field
                if 'large' in vector_fields_used:
                    print("   ✅ Data is using 'large' field (1024d)")
                    
                    # Check metadata for embedding info
                    first = samples[0]
                    if first.payload and 'metadata' in first.payload:
                        meta = first.payload['metadata']
                        if isinstance(meta, dict):
                            if 'embedding_model' in meta:
                                print(f"   Embedding model in data: {meta['embedding_model']}")
                                if 'e5-large' in meta['embedding_model']:
                                    print("   ✅ Metadata confirms e5-large")
                                else:
                                    warnings.append(f"Metadata shows different model: {meta['embedding_model']}")
                            
                            if 'embedding_dimension' in meta:
                                dim = meta['embedding_dimension']
                                print(f"   Embedding dimension in data: {dim}")
                                if dim != 1024:
                                    warnings.append(f"Metadata dimension mismatch: {dim}")
                else:
                    warnings.append(f"Data is using fields: {vector_fields_used}, not 'large'")
        else:
            print("   No data in collection yet (this is OK if just reset)")
    
    except Exception as e:
        warnings.append(f"Could not check sample data: {e}")
    
    print()
    
    # 5. Check .env files
    print("5️⃣  Configuration Files")
    print("-" * 80)
    
    env_file = Path("/srv/.env")
    env_example = Path("/srv/deployment/config/.env.example")
    
    for file_path in [env_file, env_example]:
        if file_path.exists():
            content = file_path.read_text()
            
            print(f"   {file_path.name}:")
            
            # Check for e5-large
            if "multilingual-e5-large" in content:
                print(f"      ✅ Contains e5-large")
            else:
                issues.append(f"{file_path.name} doesn't contain e5-large")
            
            # Check for EMBEDDING_DIM
            if "EMBEDDING_DIM=1024" in content or "EMBEDDING_DIM = 1024" in content:
                print(f"      ✅ EMBEDDING_DIM=1024")
            else:
                warnings.append(f"{file_path.name} missing or wrong EMBEDDING_DIM")
    
    print()
    
    # Final Report
    print("=" * 80)
    print("📊 FINAL REPORT")
    print("=" * 80)
    print()
    
    if not issues and not warnings:
        print("✅ ALL CHECKS PASSED!")
        print()
        print("   ✓ Environment variables configured for e5-large")
        print("   ✓ Embedding service ready")
        print("   ✓ Qdrant collection supports 1024d")
        print("   ✓ Configuration files updated")
        print()
        print("🎉 System is fully migrated to e5-large (1024d)")
        return 0
    
    if issues:
        print("❌ CRITICAL ISSUES FOUND:")
        for issue in issues:
            print(f"   - {issue}")
        print()
    
    if warnings:
        print("⚠️  WARNINGS:")
        for warning in warnings:
            print(f"   - {warning}")
        print()
    
    if issues:
        print("Please fix the issues above before proceeding.")
        return 1
    else:
        print("System is mostly ready, but check warnings.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
