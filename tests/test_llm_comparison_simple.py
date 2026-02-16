#!/usr/bin/env python3
"""
تست ساده مقایسه LLM ها
رویکرد: تغییر .env و restart service برای هر تنظیمات

برای کاهش زمان: فقط 5 سوال نمونه × 8 تنظیمات = 40 تست
"""
import sys
sys.path.insert(0, '/app')

import httpx
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

# تنظیمات
CORE_API_URL = "http://localhost:7001"

# 5 سوال نمونه (به جای 20)
SAMPLE_QUERIES = [
    'مالیات بر ارزش افزوده چیست و چگونه محاسبه می‌شود؟',
    'حق بیمه تامین اجتماعی چگونه محاسبه می‌شود؟',
    'تعرفه گمرکی چیست و چگونه تعیین می‌شود؟',
    'نرخ مالیات بر درآمد اشخاص حقیقی چقدر است؟',
    'سهم کارفرما و کارگر از حق بیمه چقدر است؟',
]

# تنظیمات تست - برای هر provider و model
TEST_CONFIGS = [
    {'provider': 'GapGPT', 'model': 'gpt-4o-mini', 'note': 'سبک و سریع'},
    {'provider': 'GapGPT', 'model': 'gpt-5-mini', 'note': 'نسل جدید سبک'},
    {'provider': 'GapGPT', 'model': 'gpt-5.1', 'note': 'متوسط'},
    {'provider': 'GapGPT', 'model': 'gpt-5.2-chat-latest', 'note': 'جدیدترین'},
    {'provider': 'OpenAI', 'model': 'gpt-4o-mini', 'note': 'سبک و سریع'},
    {'provider': 'OpenAI', 'model': 'gpt-4o', 'note': 'قدرتمند'},
    {'provider': 'OpenAI', 'model': 'gpt-4o', 'note': 'قدرتمند (تکرار)'},
    {'provider': 'OpenAI', 'model': 'gpt-4o', 'note': 'قدرتمند (تکرار)'},
]

def create_test_jwt():
    """ایجاد JWT برای تست"""
    from jose import jwt
    from app.config.settings import settings
    
    payload = {
        'sub': 'test_llm_comparison',
        'exp': datetime.now(timezone.utc) + timedelta(hours=2),
        'type': 'access'
    }
    
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm='HS256')
    return token

def test_single_query(query: str, token: str) -> Dict[str, Any]:
    """تست یک سوال"""
    try:
        start = time.time()
        
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
            timeout=90.0,
            follow_redirects=True
        )
        
        elapsed = (time.time() - start) * 1000
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'total_time_ms': elapsed,
                'processing_time_ms': result.get('processing_time_ms', 0),
                'tokens_used': result.get('tokens_used', 0),
                'input_tokens': result.get('input_tokens', 0),
                'output_tokens': result.get('output_tokens', 0),
                'sources_count': len(result.get('sources', [])),
                'answer_length': len(result.get('answer', ''))
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}',
                'total_time_ms': elapsed
            }
    except httpx.TimeoutException:
        return {'success': False, 'error': 'Timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)[:100]}

def main():
    print("="*80)
    print("🔬 تست ساده مقایسه LLM ها")
    print("="*80)
    print(f"⚠️  این تست از تنظیمات فعلی .env استفاده می‌کند")
    print(f"⚠️  برای تست کامل، باید .env را تغییر داده و service را restart کنید")
    print(f"\nتعداد سوالات: {len(SAMPLE_QUERIES)}")
    print(f"شروع: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # خواندن تنظیمات فعلی
    from app.config.settings import settings
    
    print(f"\n📍 تنظیمات فعلی:")
    print(f"   LLM2 Model: {settings.llm2_model}")
    print(f"   LLM2 Provider: {'GapGPT' if 'gapgpt' in settings.llm2_base_url.lower() else 'OpenAI'}")
    print(f"   LLM2 Base URL: {settings.llm2_base_url}")
    
    # ایجاد JWT
    token = create_test_jwt()
    print(f"\n✅ JWT Token ایجاد شد")
    
    # اجرای تست‌ها
    results = []
    print(f"\n🚀 شروع {len(SAMPLE_QUERIES)} تست...\n")
    
    for i, query in enumerate(SAMPLE_QUERIES, 1):
        print(f"[{i}/{len(SAMPLE_QUERIES)}] {query[:50]}...", end=' ', flush=True)
        
        result = test_single_query(query, token)
        result['query'] = query
        result['query_num'] = i
        result['provider'] = 'GapGPT' if 'gapgpt' in settings.llm2_base_url.lower() else 'OpenAI'
        result['model'] = settings.llm2_model
        results.append(result)
        
        if result['success']:
            print(f"✅ {result['total_time_ms']:.0f}ms", flush=True)
        else:
            print(f"❌ {result.get('error', 'Unknown')}", flush=True)
        
        time.sleep(0.5)
    
    # تحلیل نتایج
    successful = [r for r in results if r['success']]
    
    print("\n" + "="*80)
    print("📊 خلاصه نتایج")
    print("="*80)
    
    if successful:
        avg_total = sum(r['total_time_ms'] for r in successful) / len(successful)
        avg_proc = sum(r['processing_time_ms'] for r in successful) / len(successful)
        avg_tokens = sum(r['tokens_used'] for r in successful) / len(successful)
        
        print(f"\n✅ موفق: {len(successful)}/{len(SAMPLE_QUERIES)}")
        print(f"⏱️  میانگین زمان کل: {avg_total:.0f}ms")
        print(f"⏱️  میانگین زمان پردازش: {avg_proc:.0f}ms")
        print(f"🎫 میانگین توکن: {avg_tokens:.0f}")
    else:
        print("\n❌ همه تست‌ها ناموفق")
    
    # ذخیره نتایج
    output_data = {
        'config': {
            'provider': 'GapGPT' if 'gapgpt' in settings.llm2_base_url.lower() else 'OpenAI',
            'model': settings.llm2_model,
            'base_url': settings.llm2_base_url
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'results': results
    }
    
    output_file = f'/tmp/llm_test_{settings.llm2_model.replace(".", "_")}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 نتایج در {output_file} ذخیره شد")
    
    print("\n" + "="*80)
    print("📝 دستورالعمل تست کامل:")
    print("="*80)
    print("""
برای تست تمام ترکیبات provider+model:

1. ویرایش /srv/.env:
   LLM2_MODEL="gpt-4o-mini"  # یا gpt-5-mini, gpt-5.1, gpt-5.2-chat-latest
   LLM2_BASE_URL="https://api.gapgpt.ir/v1"  # یا https://api.openai.com/v1
   LLM2_API_KEY="..."

2. Restart service:
   cd /srv/deployment/docker
   sudo docker compose restart core-api

3. اجرای مجدد این تست:
   sudo docker compose exec core-api python /app/tests/test_llm_comparison_simple.py

4. تکرار برای هر ترکیب provider+model

5. جمع‌آوری و مقایسه نتایج از /tmp/llm_test_*.json
""")
    
    return 0 if len(successful) >= len(SAMPLE_QUERIES) * 0.8 else 1

if __name__ == '__main__':
    exit(main())
