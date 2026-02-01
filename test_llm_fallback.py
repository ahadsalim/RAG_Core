#!/usr/bin/env python3
"""
Test script for LLM fallback mechanism
Simulates primary LLM failure to test fallback
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.llm.factory import LLMWithFallback
from app.llm.base import Message, LLMConfig, LLMProvider
from app.config.settings import settings
import structlog

logger = structlog.get_logger()


async def test_fallback():
    """Test fallback by using invalid primary config"""
    print("\n" + "="*60)
    print("Testing Fallback Mechanism")
    print("="*60)
    
    # Create LLM with INVALID primary (to force fallback)
    print("\n📋 Configuration:")
    print("   Primary: INVALID URL (to simulate failure)")
    print("   Fallback: OpenAI (should work)")
    
    primary_config = LLMConfig(
        provider=LLMProvider.OPENAI_COMPATIBLE,
        model="gpt-4o-mini",
        api_key="INVALID_KEY_TO_FORCE_FAILURE",
        base_url="https://invalid-url-that-does-not-exist.com/v1",
        max_tokens=4096,
        temperature=0.7,
    )
    
    fallback_config = LLMConfig(
        provider=LLMProvider.OPENAI_COMPATIBLE,
        model=settings.llm1_fallback_model or "gpt-4o-mini",
        api_key=settings.llm1_fallback_api_key,
        base_url=settings.llm1_fallback_base_url or "https://api.openai.com/v1",
        max_tokens=4096,
        temperature=0.7,
    )
    
    llm = LLMWithFallback(
        primary_config=primary_config,
        fallback_config=fallback_config,
        timeout=5.0  # Short timeout to fail fast
    )
    
    messages = [
        Message(role="user", content="سلام! این یک تست fallback است. لطفاً یک جمله کوتاه بنویس.")
    ]
    
    print("\n📤 Sending query (primary should fail, fallback should work)...")
    
    try:
        response = await llm.generate(messages)
        
        print(f"\n✅ SUCCESS - Fallback worked!")
        print(f"   Model Used: {response.model}")
        print(f"   Response: {response.content[:150]}...")
        print(f"   Tokens: {response.usage}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED - Fallback did not work!")
        print(f"   Error: {str(e)}")
        return False


async def test_both_fail():
    """Test when both primary and fallback fail"""
    print("\n\n" + "="*60)
    print("Testing Both Primary and Fallback Failure")
    print("="*60)
    
    print("\n📋 Configuration:")
    print("   Primary: INVALID")
    print("   Fallback: INVALID")
    print("   Expected: Should raise exception")
    
    primary_config = LLMConfig(
        provider=LLMProvider.OPENAI_COMPATIBLE,
        model="gpt-4o-mini",
        api_key="INVALID_KEY",
        base_url="https://invalid-primary.com/v1",
        max_tokens=4096,
        temperature=0.7,
    )
    
    fallback_config = LLMConfig(
        provider=LLMProvider.OPENAI_COMPATIBLE,
        model="gpt-4o-mini",
        api_key="INVALID_KEY",
        base_url="https://invalid-fallback.com/v1",
        max_tokens=4096,
        temperature=0.7,
    )
    
    llm = LLMWithFallback(
        primary_config=primary_config,
        fallback_config=fallback_config,
        timeout=3.0
    )
    
    messages = [
        Message(role="user", content="Test")
    ]
    
    print("\n📤 Sending query (both should fail)...")
    
    try:
        response = await llm.generate(messages)
        print(f"\n❌ UNEXPECTED - Should have failed but got response!")
        return False
        
    except Exception as e:
        print(f"\n✅ EXPECTED FAILURE - Both failed as expected")
        print(f"   Error: {str(e)}")
        return True


async def main():
    """Main test function"""
    print("\n" + "🔴"*30)
    print("LLM Fallback Mechanism Test")
    print("🔴"*30)
    
    results = {}
    
    # Test 1: Fallback works when primary fails
    results['Fallback'] = await test_fallback()
    
    # Test 2: Both fail
    results['Both Fail'] = await test_both_fail()
    
    # Summary
    print("\n\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    
    for test_name, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All fallback tests passed!")
        return 0
    else:
        print("\n⚠️  Some fallback tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
