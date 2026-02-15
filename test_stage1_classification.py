#!/usr/bin/env python3
"""مرحله 1: تست کلاسیفیکیشن"""
import sys
sys.path.insert(0, '/app')

import httpx
import time
import json
from datetime import datetime, timezone
from app.config.settings import settings

# تنظیمات
OPENAI_KEY = settings.llm_fallback_api_key
GAPGPT_KEY = settings.llm1_api_key

# مدل‌ها برای کلاسیفیکیشن
MODELS = ['gpt-5-nano', 'gpt-4o-mini']
PROVIDERS = {
    'openai': 'https://api.openai.com/v1',
    'gapgpt': 'https://api.gapgpt.app/v1'
}

# 15 سوال کلاسیفیکیشن
QUERIES = [
    'سلام چطوری؟',
    'بذبیلذ یبل لب د دلا',
    'بیمه بیکاری چیست ؟',
    'چه خبر؟',
    'کجایی؟',
    'تهران پایتخت کجاست؟',
    'آب و هوا چطوره؟',
    'مالیات ارث چقدره ؟',
    'امروز چندمه؟',
    'فردا تعطیله؟',
    'الان کجایی؟',
    'برای واردات کالا چکار باید کرد؟',
    'نام تو چیه؟',
    'جنده کثافت دیووس؟',
    'کی تولدته؟'
]

def test_model(provider, model, query):
    """تست یک مدل با یک سوال"""
    api_key = OPENAI_KEY if provider == 'openai' else GAPGPT_KEY
    base_url = PROVIDERS[provider]
    
    try:
        start = time.time()
        response = httpx.post(
            f'{base_url}/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': query}]
            },
            timeout=90.0
        )
        elapsed = (time.time() - start) * 1000
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'time_ms': elapsed,
                'tokens': result['usage']['total_tokens'],
                'answer': result['choices'][0]['message']['content']
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
    print("مرحله 1: تست کلاسیفیکیشن")
    print("=" * 70)
    print(f"مدل‌ها: {MODELS}")
    print(f"منابع: {list(PROVIDERS.keys())}")
    print(f"تعداد سوالات: {len(QUERIES)}")
    print(f"مجموع تست‌ها: {len(MODELS)} × {len(PROVIDERS)} × {len(QUERIES)} = {len(MODELS) * len(PROVIDERS) * len(QUERIES)}")
    print("=" * 70)
    
    results = {}
    total_tests = len(MODELS) * len(PROVIDERS) * len(QUERIES)
    current_test = 0
    
    for model in MODELS:
        for provider in PROVIDERS.keys():
            key = f'{provider}_{model}'
            results[key] = []
            
            print(f"\n🔍 تست {key}:")
            
            for i, query in enumerate(QUERIES, 1):
                current_test += 1
                print(f"  [{current_test}/{total_tests}] سوال {i}/15: {query[:40]}...", end=' ', flush=True)
                
                result = test_model(provider, model, query)
                results[key].append({
                    'query': query,
                    'result': result
                })
                
                if result['success']:
                    print(f"✅ {result['time_ms']:.0f}ms", flush=True)
                else:
                    print(f"❌ {result.get('error', 'Unknown')}", flush=True)
                
                # استراحت کوتاه بین درخواست‌ها
                if result['success']:
                    time.sleep(0.3)
    
    # ذخیره نتایج
    output_file = '/srv/test_results_stage1_classification.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 70)
    print("📊 خلاصه نتایج مرحله 1:")
    print("=" * 70)
    
    for key, data in results.items():
        successful = [r['result'] for r in data if r['result']['success']]
        if successful:
            times = [r['time_ms'] for r in successful]
            avg_time = sum(times) / len(times)
            avg_tokens = sum(r['tokens'] for r in successful) / len(successful)
            print(f"{key:25s}: {len(successful)}/15 موفق | میانگین: {avg_time:6.1f}ms | توکن: {avg_tokens:.0f}")
        else:
            print(f"{key:25s}: ❌ همه تست‌ها ناموفق")
    
    print(f"\n✅ نتایج در {output_file} ذخیره شد")
    return 0

if __name__ == '__main__':
    exit(main())
