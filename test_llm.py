#!/usr/bin/env python3
"""
Test script for LLM primary and fallback
Tests both LLM1 (Light) and LLM2 (Pro) with their fallback configurations
"""

import asyncio
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.llm.factory import create_llm1_light, create_llm2_pro
from app.llm.base import Message
from app.config.settings import settings
import structlog

logger = structlog.get_logger()


async def test_llm(llm_name: str, llm_instance):
    """Test a specific LLM instance"""
    print(f"\n{'='*60}")
    print(f"Testing {llm_name}")
    print(f"{'='*60}")
    
    # Test message
    messages = [
        Message(role="user", content="سلام! لطفاً یک جمله کوتاه فارسی بنویس و بگو چه مدلی هستی.")
    ]
    
    print(f"\n📤 Sending test query to {llm_name}...")
    print(f"   Primary Model: {llm_instance.primary_config.model}")
    print(f"   Primary URL: {llm_instance.primary_config.base_url}")
    
    if llm_instance.fallback_config:
        print(f"   Fallback Model: {llm_instance.fallback_config.model}")
        print(f"   Fallback URL: {llm_instance.fallback_config.base_url}")
    else:
        print(f"   ⚠️  No fallback configured")
    
    try:
        # Try to get response
        response = await llm_instance.generate(messages)
        
        print(f"\n✅ SUCCESS!")
        print(f"   Model Used: {response.model}")
        print(f"   Response: {response.content[:200]}...")
        print(f"   Tokens Used: {response.usage}")
        print(f"   Finish Reason: {response.finish_reason}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED!")
        print(f"   Error: {str(e)}")
        return False


async def main():
    """Main test function"""
    print("\n" + "="*60)
    print("LLM Primary & Fallback Test")
    print("="*60)
    
    print(f"\n📋 Configuration:")
    print(f"   Primary Timeout: {settings.llm_primary_timeout}s")
    print(f"   Web Search Timeout: {settings.llm_web_search_timeout}s")
    
    results = {}
    
    # Test LLM1 (Light)
    print("\n\n" + "🔵"*30)
    print("Testing LLM1 (Light) - For simple queries")
    print("🔵"*30)
    llm1 = create_llm1_light()
    results['LLM1'] = await test_llm("LLM1 (Light)", llm1)
    
    # Test LLM2 (Pro)
    print("\n\n" + "🟢"*30)
    print("Testing LLM2 (Pro) - For business queries")
    print("🟢"*30)
    llm2 = create_llm2_pro()
    results['LLM2'] = await test_llm("LLM2 (Pro)", llm2)
    
    # Summary
    print("\n\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    
    for llm_name, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"   {llm_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
