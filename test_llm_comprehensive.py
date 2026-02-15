#!/usr/bin/env python3
"""تست جامع مدل‌های LLM"""
import sys
sys.path.insert(0, '/app')

import httpx
import time
import json
from datetime import datetime, timezone
from jose import jwt

# تنظیمات
JWT_SECRET = '4d0y3u2WuICdKEIGY5n5XoHUkIHKE2v9oq9MsfGIWNgqpIdVnxYSSkd2YT3C5fZs'

# دریافت API keys از settings
from app.config.settings import settings
OPENAI_KEY = settings.llm_fallback_api_key
GAPGPT_KEY = settings.llm1_api_key

# مدل‌ها برای تست
MODELS = ['gpt-5-nano', 'gpt-4o-mini', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.2']
PROVIDERS = {
    'openai': 'https://api.openai.com/v1',
    'gapgpt': 'https://api.gapgpt.app/v1'
}

# سوالات تست
CLASSIFICATION_QUERIES = [
    'سلام چطوری؟', 'خوبی؟', 'حالت چطوره؟', 'چه خبر؟', 'کجایی؟',
    'تهران پایتخت کجاست؟', 'آب و هوا چطوره؟', 'ساعت چنده؟', 
    'امروز چندمه؟', 'فردا تعطیله؟', 'الان کجایی؟', 'چیکار می‌کنی؟',
    'نام تو چیه؟', 'چند سالته؟', 'کی تولدته؟'
]

GENERAL_QUERIES = [
    'تهران پایتخت کدام کشور است؟', 'مساحت ایران چقدر است؟',
    'جمعیت تهران چقدر است؟', 'بلندترین کوه ایران کدام است؟',
    'دریاچه ارومیه کجاست؟', 'رود کارون کجاست؟', 'خلیج فارس کجاست؟',
    'صنایع ایران چیست؟', 'محصولات کشاورزی ایران چیست؟',
    'آب و هوای ایران چگونه است؟', 'فصل‌های ایران چیست؟',
    'زبان رسمی ایران چیست؟', 'پول ایران چیست؟', 'پرچم ایران چه رنگی است؟',
    'سرود ملی ایران چیست؟', 'روز ملی ایران چه روزی است؟',
    'تاریخ ایران چقدر قدیمی است؟', 'تمدن ایران چگونه بود؟',
    'شاعران ایران کی‌اند؟', 'نویسندگان ایران کی‌اند؟'
]

BUSINESS_QUERIES = [
    'در لیست حقوق و دستمزد چند درصد بابت بیمه بیکاری کسر کنم؟',
    'حق بیمه سهم کارفرما چند درصد است؟', 'حق بیمه سهم کارگر چند درصد است؟',
    'مرخصی استعلاجی چند روز است؟', 'مرخصی زایمان چند روز است؟',
    'مرخصی سالانه چند روز است؟', 'حداقل دستمزد چقدر است؟',
    'عیدی چقدر است؟', 'پاداش چقدر است؟', 'اضافه کار چگونه محاسبه می‌شود؟',
    'کسر کار چگونه محاسبه می‌شود؟', 'مالیات حقوق چند درصد است؟',
    'بیمه تکمیلی چیست؟', 'بیمه عمر چیست؟', 'بیمه حوادث چیست؟',
    'قرارداد کار چیست؟', 'قرارداد موقت چیست؟', 'قرارداد دائم چیست؟',
    'اخراج چگونه است؟', 'استعفا چگونه است؟'
]

def generate_jwt():
    """تولید JWT token"""
    payload = {'sub': 'test-user', 'exp': datetime.now(timezone.utc).timestamp() + 3600}
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def test_direct_llm(provider, model, query):
    """تست مستقیم LLM (بدون RAG)"""
    api_key = OPENAI_KEY if provider == 'openai' else GAPGPT_KEY
    base_url = PROVIDERS[provider]
    
    try:
        start = time.time()
        response = httpx.post(
            f'{base_url}/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={'model': model, 'messages': [{'role': 'user', 'content': query}]},
            timeout=120.0
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
            return {'success': False, 'error': f'HTTP {response.status_code}', 'time_ms': elapsed}
    except Exception as e:
        return {'success': False, 'error': str(e)[:100]}

def test_rag_query(provider, model, query):
    """تست با RAG (از طریق Core API)"""
    token = generate_jwt()
    
    # موقتاً تنظیمات را تغییر دهیم
    # این باید از طریق environment variable یا API انجام شود
    # برای سادگی، فقط زمان را اندازه می‌گیریم
    
    try:
        start = time.time()
        response = httpx.post(
            'http://localhost:7001/api/v1/query/',
            json={
                'query': query,
                'conversation_id': None,
                'language': 'fa',
                'file_attachments': [],
                'enable_web_search': False
            },
            headers={'Authorization': f'Bearer {token}'},
            timeout=120.0
        )
        elapsed = (time.time() - start) * 1000
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'time_ms': elapsed,
                'tokens': result.get('tokens_used', 0),
                'answer': result.get('answer', '')
            }
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}', 'time_ms': elapsed}
    except Exception as e:
        return {'success': False, 'error': str(e)[:100]}

def main():
    print("🚀 شروع تست جامع مدل‌های LLM")
    print("=" * 70)
    
    results = {
        'classification': {},
        'general': {},
        'business': {}
    }
    
    # تست کلاسیفیکیشن (فقط 5 سوال برای سرعت)
    print("\n📊 تست کلاسیفیکیشن (5 سوال)...")
    for model in ['gpt-5-nano', 'gpt-4o-mini']:
        for provider in ['openai', 'gapgpt']:
            key = f'{provider}_{model}'
            results['classification'][key] = []
            
            for i, query in enumerate(CLASSIFICATION_QUERIES[:5], 1):
                print(f"  {i}/5: {provider} - {model}")
                result = test_direct_llm(provider, model, query)
                results['classification'][key].append(result)
                time.sleep(0.5)
    
    # ذخیره نتایج
    with open('/srv/llm_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n✅ تست کامل شد. نتایج در /srv/llm_test_results.json ذخیره شد.")

if __name__ == '__main__':
    main()
