#!/usr/bin/env python3
"""
تست جامع 20 سوال تجاری با تحلیل دقیق زمان‌بندی هر مرحله
هدف: شناسایی گلوگاه‌های زمانی و مقایسه عملکرد OpenAI vs GapGPT
"""
import sys
sys.path.insert(0, '/app')

import httpx
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from app.config.settings import settings

# تنظیمات
JWT_SECRET = settings.jwt_secret_key
CORE_API_URL = "http://localhost:7001"

# 20 سوال تخصصی متنوع
BUSINESS_QUERIES = [
    # مالیات (7 سوال)
    'مالیات بر ارزش افزوده چیست و چگونه محاسبه می‌شود؟',
    'نرخ مالیات بر درآمد اشخاص حقیقی چقدر است؟',
    'معافیت مالیاتی حقوق چگونه محاسبه می‌شود؟',
    'مالیات بر اجاره املاک چگونه پرداخت می‌شود؟',
    'مهلت تسلیم اظهارنامه مالیاتی چه زمانی است؟',
    'جرایم عدم پرداخت به موقع مالیات چقدر است؟',
    'مالیات شرکت‌ها چگونه محاسبه می‌شود؟',
    
    # بیمه کارگری (7 سوال)
    'حق بیمه تامین اجتماعی چگونه محاسبه می‌شود؟',
    'سهم کارفرما و کارگر از حق بیمه چقدر است؟',
    'شرایط دریافت بیمه بیکاری چیست؟',
    'مدت پرداخت بیمه بیکاری چقدر است؟',
    'بیمه حوادث کار چه مواردی را پوشش می‌دهد؟',
    'سنوات بازنشستگی در تامین اجتماعی چقدر است؟',
    'نحوه محاسبه مستمری بازنشستگی چگونه است؟',
    
    # گمرک (6 سوال)
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
    
    payload = {
        'sub': 'test_user_timing_analysis',
        'exp': datetime.now(timezone.utc) + timedelta(hours=2),
        'type': 'access'
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return token

def test_query_with_timing(query: str, token: str, query_num: int) -> Dict[str, Any]:
    """
    تست یک سوال با اندازه‌گیری دقیق زمان هر مرحله
    """
    timings = {
        'total_start': time.time(),
        'request_sent': None,
        'response_received': None,
        'total_end': None
    }
    
    try:
        # ارسال درخواست
        timings['request_sent'] = time.time()
        
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
        
        timings['response_received'] = time.time()
        timings['total_end'] = time.time()
        
        # محاسبه زمان‌ها
        network_time = (timings['response_received'] - timings['request_sent']) * 1000
        total_time = (timings['total_end'] - timings['total_start']) * 1000
        
        if response.status_code == 200:
            result = response.json()
            
            # استخراج اطلاعات timing از response
            processing_time = result.get('processing_time_ms', 0)
            
            return {
                'success': True,
                'query': query,
                'query_num': query_num,
                
                # زمان‌ها (ms)
                'total_time_ms': total_time,
                'network_time_ms': network_time,
                'processing_time_ms': processing_time,
                'overhead_time_ms': total_time - processing_time,
                
                # اطلاعات LLM
                'tokens_used': result.get('tokens_used', 0),
                'input_tokens': result.get('input_tokens', 0),
                'output_tokens': result.get('output_tokens', 0),
                
                # اطلاعات RAG
                'sources_count': len(result.get('sources', [])),
                'context_used': result.get('context_used', False),
                
                # پاسخ
                'answer_length': len(result.get('answer', '')),
                'answer_preview': result.get('answer', '')[:200],
                
                # متادیتا
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        else:
            return {
                'success': False,
                'query': query,
                'query_num': query_num,
                'error': f'HTTP {response.status_code}',
                'total_time_ms': total_time,
                'response_text': response.text[:300],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
    except httpx.TimeoutException as e:
        return {
            'success': False,
            'query': query,
            'query_num': query_num,
            'error': 'Timeout',
            'error_detail': str(e)[:200],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            'success': False,
            'query': query,
            'query_num': query_num,
            'error': type(e).__name__,
            'error_detail': str(e)[:200],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

def analyze_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """تحلیل نتایج و شناسایی گلوگاه‌ها"""
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    if not successful:
        return {
            'success_rate': 0,
            'total_queries': len(results),
            'failed_count': len(failed),
            'errors': [{'query': r['query'][:50], 'error': r.get('error')} for r in failed]
        }
    
    # محاسبه میانگین‌ها
    total_times = [r['total_time_ms'] for r in successful]
    network_times = [r['network_time_ms'] for r in successful]
    processing_times = [r['processing_time_ms'] for r in successful]
    overhead_times = [r['overhead_time_ms'] for r in successful]
    
    tokens_used = [r['tokens_used'] for r in successful]
    input_tokens = [r['input_tokens'] for r in successful]
    output_tokens = [r['output_tokens'] for r in successful]
    sources = [r['sources_count'] for r in successful]
    
    analysis = {
        # آمار کلی
        'success_rate': len(successful) / len(results) * 100,
        'total_queries': len(results),
        'successful_count': len(successful),
        'failed_count': len(failed),
        
        # تحلیل زمانی (ms)
        'timing_analysis': {
            'total_time': {
                'avg': sum(total_times) / len(total_times),
                'min': min(total_times),
                'max': max(total_times),
                'median': sorted(total_times)[len(total_times)//2]
            },
            'network_time': {
                'avg': sum(network_times) / len(network_times),
                'min': min(network_times),
                'max': max(network_times),
                'percentage': (sum(network_times) / sum(total_times)) * 100
            },
            'processing_time': {
                'avg': sum(processing_times) / len(processing_times),
                'min': min(processing_times),
                'max': max(processing_times),
                'percentage': (sum(processing_times) / sum(total_times)) * 100
            },
            'overhead_time': {
                'avg': sum(overhead_times) / len(overhead_times),
                'min': min(overhead_times),
                'max': max(overhead_times),
                'percentage': (sum(overhead_times) / sum(total_times)) * 100
            }
        },
        
        # تحلیل توکن‌ها
        'token_analysis': {
            'total_tokens': {
                'avg': sum(tokens_used) / len(tokens_used),
                'min': min(tokens_used),
                'max': max(tokens_used),
                'total': sum(tokens_used)
            },
            'input_tokens': {
                'avg': sum(input_tokens) / len(input_tokens),
                'total': sum(input_tokens)
            },
            'output_tokens': {
                'avg': sum(output_tokens) / len(output_tokens),
                'total': sum(output_tokens)
            }
        },
        
        # تحلیل RAG
        'rag_analysis': {
            'avg_sources': sum(sources) / len(sources),
            'min_sources': min(sources),
            'max_sources': max(sources),
            'context_usage_rate': sum(1 for r in successful if r['context_used']) / len(successful) * 100
        },
        
        # گلوگاه‌های زمانی
        'bottlenecks': identify_bottlenecks(successful),
        
        # خطاها
        'errors': [{'query': r['query'][:50], 'error': r.get('error')} for r in failed] if failed else []
    }
    
    return analysis

def identify_bottlenecks(successful_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """شناسایی گلوگاه‌های زمانی"""
    if not successful_results:
        return {}
    
    # محاسبه میانگین هر بخش
    avg_network = sum(r['network_time_ms'] for r in successful_results) / len(successful_results)
    avg_processing = sum(r['processing_time_ms'] for r in successful_results) / len(successful_results)
    avg_overhead = sum(r['overhead_time_ms'] for r in successful_results) / len(successful_results)
    avg_total = sum(r['total_time_ms'] for r in successful_results) / len(successful_results)
    
    # شناسایی بزرگترین گلوگاه
    components = {
        'network': avg_network,
        'processing': avg_processing,
        'overhead': avg_overhead
    }
    
    main_bottleneck = max(components, key=components.get)
    
    return {
        'main_bottleneck': main_bottleneck,
        'main_bottleneck_time_ms': components[main_bottleneck],
        'main_bottleneck_percentage': (components[main_bottleneck] / avg_total) * 100,
        'breakdown': {
            'network_ms': avg_network,
            'processing_ms': avg_processing,
            'overhead_ms': avg_overhead,
            'total_ms': avg_total
        },
        'recommendations': generate_recommendations(main_bottleneck, components)
    }

def generate_recommendations(bottleneck: str, components: Dict[str, float]) -> List[str]:
    """تولید توصیه‌های بهینه‌سازی بر اساس گلوگاه"""
    recommendations = []
    
    if bottleneck == 'processing':
        recommendations.extend([
            'بهینه‌سازی LLM: استفاده از مدل سریعتر (مثلاً gpt-4o-mini به جای gpt-4o)',
            'کاهش context window: محدود کردن تعداد chunks ارسالی به LLM',
            'بررسی reranker: زمان reranking ممکن است زیاد باشد',
            'استفاده از caching برای سوالات تکراری'
        ])
    elif bottleneck == 'network':
        recommendations.extend([
            'بررسی اتصال شبکه به سرویس‌های خارجی (OpenAI/GapGPT)',
            'استفاده از CDN یا proxy نزدیک‌تر',
            'افزایش timeout و retry mechanism',
            'بررسی latency به سرور LLM'
        ])
    elif bottleneck == 'overhead':
        recommendations.extend([
            'بهینه‌سازی Qdrant query: کاهش زمان جستجو در vector DB',
            'بهینه‌سازی embedding: استفاده از مدل سریعتر یا local embedding',
            'کاهش overhead سریالیزاسیون و پردازش داده',
            'بررسی performance database queries'
        ])
    
    return recommendations

def print_summary(analysis: Dict[str, Any], config: Dict[str, str]):
    """چاپ خلاصه نتایج"""
    print("\n" + "=" * 80)
    print("📊 تحلیل جامع عملکرد سیستم RAG")
    print("=" * 80)
    
    print(f"\n🎯 تنظیمات فعلی:")
    print(f"   LLM2 Primary: {config['llm2_model']} ({config['llm2_provider']})")
    print(f"   LLM2 Fallback: {config['llm2_fallback_model']} ({config['llm2_fallback_provider']})")
    print(f"   Reranker: {config['reranker_url']}")
    
    print(f"\n✅ نرخ موفقیت: {analysis['success_rate']:.1f}% ({analysis['successful_count']}/{analysis['total_queries']})")
    
    if analysis['success_rate'] > 0:
        timing = analysis['timing_analysis']
        
        print(f"\n⏱️  تحلیل زمانی (میانگین):")
        print(f"   کل زمان: {timing['total_time']['avg']:.0f}ms")
        print(f"   ├─ شبکه: {timing['network_time']['avg']:.0f}ms ({timing['network_time']['percentage']:.1f}%)")
        print(f"   ├─ پردازش: {timing['processing_time']['avg']:.0f}ms ({timing['processing_time']['percentage']:.1f}%)")
        print(f"   └─ overhead: {timing['overhead_time']['avg']:.0f}ms ({timing['overhead_time']['percentage']:.1f}%)")
        
        print(f"\n   محدوده زمانی: {timing['total_time']['min']:.0f}ms - {timing['total_time']['max']:.0f}ms")
        print(f"   میانه: {timing['total_time']['median']:.0f}ms")
        
        tokens = analysis['token_analysis']
        print(f"\n🎫 مصرف توکن:")
        print(f"   میانگین: {tokens['total_tokens']['avg']:.0f} (ورودی: {tokens['input_tokens']['avg']:.0f}, خروجی: {tokens['output_tokens']['avg']:.0f})")
        print(f"   کل: {tokens['total_tokens']['total']:.0f} توکن")
        
        rag = analysis['rag_analysis']
        print(f"\n📚 عملکرد RAG:")
        print(f"   میانگین منابع: {rag['avg_sources']:.1f}")
        print(f"   استفاده از context: {rag['context_usage_rate']:.1f}%")
        
        bottlenecks = analysis['bottlenecks']
        print(f"\n🚨 گلوگاه اصلی: {bottlenecks['main_bottleneck'].upper()}")
        print(f"   زمان: {bottlenecks['main_bottleneck_time_ms']:.0f}ms ({bottlenecks['main_bottleneck_percentage']:.1f}%)")
        
        print(f"\n💡 توصیه‌های بهینه‌سازی:")
        for i, rec in enumerate(bottlenecks['recommendations'], 1):
            print(f"   {i}. {rec}")
    
    if analysis['failed_count'] > 0:
        print(f"\n❌ خطاها ({analysis['failed_count']}):")
        for err in analysis['errors'][:5]:
            print(f"   - {err['query']}: {err['error']}")

def main():
    print("=" * 80)
    print("🔬 تست جامع عملکرد سیستم RAG - تحلیل زمانی دقیق")
    print("=" * 80)
    print(f"تعداد سوالات: {len(BUSINESS_QUERIES)}")
    print(f"شروع: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # جمع‌آوری تنظیمات
    config = {
        'llm2_model': settings.llm2_model,
        'llm2_provider': 'GapGPT' if 'gapgpt' in settings.llm2_base_url.lower() else 'OpenAI',
        'llm2_fallback_model': settings.llm2_fallback_model,
        'llm2_fallback_provider': 'OpenAI' if 'openai' in settings.llm2_fallback_base_url.lower() else 'Unknown',
        'reranker_url': settings.reranker_service_url
    }
    
    # ایجاد JWT
    token = create_test_jwt()
    print(f"\n✅ JWT Token ایجاد شد")
    
    # اجرای تست‌ها
    results = []
    print(f"\n🚀 شروع تست {len(BUSINESS_QUERIES)} سوال...\n")
    
    for i, query in enumerate(BUSINESS_QUERIES, 1):
        print(f"[{i:2d}/{len(BUSINESS_QUERIES)}] {query[:60]}...", end=' ', flush=True)
        
        result = test_query_with_timing(query, token, i)
        results.append(result)
        
        if result['success']:
            print(f"✅ {result['total_time_ms']:.0f}ms", flush=True)
        else:
            print(f"❌ {result.get('error', 'Unknown')}", flush=True)
        
        # استراحت کوتاه
        if i < len(BUSINESS_QUERIES):
            time.sleep(0.5)
    
    # تحلیل نتایج
    analysis = analyze_results(results)
    
    # ذخیره نتایج
    output_data = {
        'config': config,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'queries_count': len(BUSINESS_QUERIES),
        'results': results,
        'analysis': analysis
    }
    
    output_file = '/tmp/business_timing_analysis.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    # چاپ خلاصه
    print_summary(analysis, config)
    
    print(f"\n💾 نتایج کامل در {output_file} ذخیره شد")
    print("\n📖 برای مشاهده جزئیات:")
    print(f"   cat {output_file} | jq '.analysis'")
    print(f"   cat {output_file} | jq '.results[] | select(.success==false)'")
    
    return 0 if analysis['success_rate'] >= 80 else 1

if __name__ == '__main__':
    exit(main())
