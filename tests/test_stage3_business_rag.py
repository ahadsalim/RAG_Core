#!/usr/bin/env python3
"""مرحله 3: تست سوالات تخصصی با RAG - با تنظیمات فعلی"""
import sys
sys.path.insert(0, '/app')

import httpx
import time
import json
from app.config.settings import settings

# تنظیمات
JWT_SECRET = settings.jwt_secret_key
CORE_API_URL = "http://localhost:7001"

# 20 سوال تخصصی مالیات / بیمه کارگری / گمرک
QUERIES = [
    # سوالات مالیاتی (7 سوال)
    'مالیات بر ارزش افزوده چیست و چگونه محاسبه می‌شود؟',
    'نرخ مالیات بر درآمد اشخاص حقیقی چقدر است؟',
    'معافیت مالیاتی حقوق چگونه محاسبه می‌شود؟',
    'مالیات بر اجاره املاک چگونه پرداخت می‌شود؟',
    'مهلت تسلیم اظهارنامه مالیاتی چه زمانی است؟',
    'جرایم عدم پرداخت به موقع مالیات چقدر است؟',
    'مالیات شرکت‌ها چگونه محاسبه می‌شود؟',
    
    # سوالات بیمه کارگری (7 سوال)
    'حق بیمه تامین اجتماعی چگونه محاسبه می‌شود؟',
    'سهم کارفرما و کارگر از حق بیمه چقدر است؟',
    'شرایط دریافت بیمه بیکاری چیست؟',
    'مدت پرداخت بیمه بیکاری چقدر است؟',
    'بیمه حوادث کار چه مواردی را پوشش می‌دهد؟',
    'سنوات بازنشستگی در تامین اجتماعی چقدر است؟',
    'نحوه محاسبه مستمری بازنشستگی چگونه است؟',
    
    # سوالات گمرکی (6 سوال)
    'تعرفه گمرکی چیست و چگونه تعیین می‌شود؟',
    'حقوق ورودی کالا چگونه محاسبه می‌شود؟',
    'مالیات بر واردات چقدر است؟',
    'مدارک مورد نیاز برای ترخیص کالا از گمرک چیست؟',
    'معافیت گمرکی در چه مواردی اعمال می‌شود؟',
    'جریمه عدم اظهار کالا در گمرک چقدر است؟'
]

def create_test_jwt():
    """ایجاد JWT برای تست"""
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    
    payload = {
        'sub': 'test_user_benchmark',
        'exp': datetime.now(timezone.utc) + timedelta(hours=1),
        'type': 'access'
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return token

def test_business_query(query, token):
    """تست یک سوال تخصصی از طریق Core API با RAG"""
    try:
        start = time.time()
        
        # ارسال درخواست به Core API
        response = httpx.post(
            f'{CORE_API_URL}/api/v1/query',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            },
            json={
                'query': query,
                'language': 'fa',
                'enable_web_search': False
            },
            timeout=120.0,
            follow_redirects=True
        )
        
        elapsed = (time.time() - start) * 1000
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'time_ms': elapsed,
                'tokens': result.get('tokens_used', 0),
                'answer': result.get('answer', ''),
                'sources_count': len(result.get('sources', [])),
                'context_used': result.get('context_used', False),
                'processing_time_ms': result.get('processing_time_ms', 0),
                'input_tokens': result.get('input_tokens', 0),
                'output_tokens': result.get('output_tokens', 0)
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}',
                'time_ms': elapsed,
                'response': response.text[:200]
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)[:100],
            'time_ms': 0
        }

def main():
    print("=" * 70)
    print("مرحله 3: تست سوالات تخصصی با RAG")
    print("=" * 70)
    print(f"تعداد سوالات: {len(QUERIES)}")
    print("=" * 70)
    print("\n📌 تنظیمات فعلی:")
    print(f"   - LLM2 Model: {settings.llm2_model}")
    print(f"   - LLM2 Provider: {'GapGPT' if 'gapgpt' in settings.llm2_base_url else 'OpenAI'}")
    print(f"   - Fallback Model: {settings.llm2_fallback_model}")
    print(f"   - Fallback Provider: {'OpenAI' if 'openai' in settings.llm2_fallback_base_url else 'Unknown'}")
    print("\n⚠️  این تست‌ها از طریق Core API و سیستم RAG اجرا می‌شوند")
    print("⚠️  سوالات به صورت business_no_file دسته‌بندی می‌شوند و از RAG استفاده می‌کنند\n")
    
    # ایجاد JWT
    token = create_test_jwt()
    print(f"✅ JWT Token ایجاد شد\n")
    
    results = []
    
    for i, query in enumerate(QUERIES, 1):
        print(f"[{i}/{len(QUERIES)}] سوال: {query[:50]}...", end=' ', flush=True)
        
        result = test_business_query(query, token)
        results.append({
            'query': query,
            'result': result
        })
        
        if result['success']:
            sources = result.get('sources_count', 0)
            proc_time = result.get('processing_time_ms', 0)
            print(f"✅ {result['time_ms']:.0f}ms (proc: {proc_time:.0f}ms) | {sources} منبع", flush=True)
        else:
            print(f"❌ {result.get('error', 'Unknown')}", flush=True)
        
        # استراحت کوتاه بین درخواست‌ها
        if result['success']:
            time.sleep(0.5)
    
    # ذخیره نتایج در /tmp
    output_file = '/tmp/test_results_stage3_business_rag.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 70)
    print("📊 خلاصه نتایج مرحله 3:")
    print("=" * 70)
    
    successful = [r['result'] for r in results if r['result']['success']]
    
    if successful:
        times = [r['time_ms'] for r in successful]
        proc_times = [r.get('processing_time_ms', 0) for r in successful]
        tokens = [r.get('tokens', 0) for r in successful]
        sources = [r.get('sources_count', 0) for r in successful]
        
        print(f"موفق: {len(successful)}/{len(QUERIES)}")
        print(f"میانگین زمان کل: {sum(times)/len(times):.1f}ms")
        print(f"میانگین زمان پردازش: {sum(proc_times)/len(proc_times):.1f}ms")
        print(f"میانگین توکن: {sum(tokens)/len(tokens):.0f}")
        print(f"میانگین منابع: {sum(sources)/len(sources):.1f}")
        print(f"حداقل زمان: {min(times):.0f}ms")
        print(f"حداکثر زمان: {max(times):.0f}ms")
    else:
        print("❌ همه تست‌ها ناموفق")
    
    print(f"\n✅ نتایج در {output_file} ذخیره شد")
    print("\n💡 برای مشاهده نمونه پاسخ‌ها:")
    print(f"   cat {output_file} | jq '.[] | {{query: .query, answer: .result.answer[:100], sources: .result.sources_count}}'")
    
    return 0

if __name__ == '__main__':
    exit(main())
