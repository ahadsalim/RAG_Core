#!/usr/bin/env python3
"""
تست اتصال به LLM خارجی
"""

import asyncio
import sys
from openai import AsyncOpenAI

# تنظیمات از .env
LLM_API_KEY = "sk-QGiGf0uwYr2mqmCUR1zUMQVSwU4t8if48aspRjGalnum9zIE"
LLM_BASE_URL = "https://api.gapgpt.app/v1"
LLM_MODEL = "gpt-4o-mini"

async def test_llm_connection():
    """تست اتصال به LLM"""
    
    print("🧪 تست اتصال به LLM...")
    print(f"Base URL: {LLM_BASE_URL}")
    print(f"Model: {LLM_MODEL}")
    print(f"API Key: {LLM_API_KEY[:20]}...")
    print("-" * 60)
    
    try:
        # ایجاد client
        client = AsyncOpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL
        )
        
        print("\n📤 ارسال درخواست ساده...")
        
        # تست با timeout
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "سلام"}
                ],
                max_tokens=50,
                temperature=0.2
            ),
            timeout=10.0  # 10 ثانیه timeout
        )
        
        print("\n✅ موفق! پاسخ دریافت شد:")
        print(f"Content: {response.choices[0].message.content}")
        print(f"Model: {response.model}")
        print(f"Tokens: {response.usage.total_tokens if response.usage else 'N/A'}")
        
        return True
        
    except asyncio.TimeoutError:
        print("\n❌ Timeout! LLM بیش از 10 ثانیه پاسخ نداد.")
        print("علت احتمالی:")
        print("  - سرور LLM کند است")
        print("  - شبکه مشکل دارد")
        print("  - Base URL اشتباه است")
        return False
        
    except Exception as e:
        print(f"\n❌ خطا: {type(e).__name__}")
        print(f"پیام: {str(e)}")
        
        if "401" in str(e) or "Unauthorized" in str(e):
            print("\n🔑 API Key نامعتبر است!")
        elif "404" in str(e):
            print("\n🔍 Base URL یا Model اشتباه است!")
        elif "Connection" in str(e):
            print("\n🔌 اتصال به سرور برقرار نشد!")
        
        return False


async def test_with_different_timeouts():
    """تست با timeout های مختلف"""
    
    print("\n" + "=" * 60)
    print("🧪 تست با timeout های مختلف...")
    print("=" * 60)
    
    client = AsyncOpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL
    )
    
    for timeout in [2, 5, 10, 30]:
        print(f"\n⏱️ تست با timeout {timeout} ثانیه...")
        
        try:
            start = asyncio.get_event_loop().time()
            
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[{"role": "user", "content": "سلام"}],
                    max_tokens=10
                ),
                timeout=timeout
            )
            
            elapsed = asyncio.get_event_loop().time() - start
            print(f"  ✅ موفق در {elapsed:.2f} ثانیه")
            return True
            
        except asyncio.TimeoutError:
            print(f"  ❌ Timeout بعد از {timeout} ثانیه")
            continue
        except Exception as e:
            print(f"  ❌ خطا: {str(e)[:100]}")
            return False
    
    print("\n❌ همه timeout ها شکست خوردند!")
    return False


if __name__ == "__main__":
    print("=" * 60)
    print("تست اتصال به LLM خارجی (GapGPT)")
    print("=" * 60)
    
    # تست اصلی
    result = asyncio.run(test_llm_connection())
    
    if not result:
        # اگر شکست خورد، با timeout های مختلف تست کن
        asyncio.run(test_with_different_timeouts())
    
    print("\n" + "=" * 60)
    print("پایان تست")
    print("=" * 60)
    
    sys.exit(0 if result else 1)
