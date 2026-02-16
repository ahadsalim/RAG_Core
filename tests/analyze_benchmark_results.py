#!/usr/bin/env python3
"""تحلیل و مقایسه نتایج benchmark های LLM"""
import json
import glob
from typing import List, Dict, Any
from pathlib import Path

def load_all_results() -> List[Dict[str, Any]]:
    """بارگذاری تمام فایل‌های نتایج"""
    results = []
    pattern = '/tmp/llm_test_*.json'
    
    for filepath in glob.glob(pattern):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                results.append(data)
        except Exception as e:
            print(f"خطا در خواندن {filepath}: {e}")
    
    return results

def analyze_results(all_results: List[Dict[str, Any]]):
    """تحلیل و مقایسه نتایج"""
    
    print("="*80)
    print("📊 تحلیل جامع نتایج Benchmark")
    print("="*80)
    print(f"\nتعداد تنظیمات تست شده: {len(all_results)}")
    
    # جدول مقایسه
    print("\n" + "="*80)
    print("جدول مقایسه Provider و Model")
    print("="*80)
    print(f"{'Provider':<10} {'Model':<25} {'موفق':<8} {'کل(ms)':<10} {'پردازش(ms)':<12} {'توکن':<8}")
    print("-"*80)
    
    summary_data = []
    
    for data in all_results:
        config = data['config']
        results = data['results']
        
        successful = [r for r in results if r['success']]
        if not successful:
            continue
        
        provider = config['provider']
        model = config['model']
        count = len(successful)
        total_queries = len(results)
        
        avg_total = sum(r['total_time_ms'] for r in successful) / count
        avg_proc = sum(r['processing_time_ms'] for r in successful) / count
        avg_tokens = sum(r['tokens_used'] for r in successful) / count
        
        summary_data.append({
            'provider': provider,
            'model': model,
            'count': count,
            'total': total_queries,
            'avg_total_ms': avg_total,
            'avg_proc_ms': avg_proc,
            'avg_tokens': avg_tokens
        })
        
        print(f"{provider:<10} {model:<25} {count}/{total_queries:<6} {avg_total:<10.0f} {avg_proc:<12.0f} {avg_tokens:<8.0f}")
    
    # بهترین‌ها
    if summary_data:
        print("\n" + "="*80)
        print("🏆 بهترین‌ها")
        print("="*80)
        
        fastest = min(summary_data, key=lambda x: x['avg_total_ms'])
        print(f"\n⚡ سریع‌ترین: {fastest['provider']} - {fastest['model']}")
        print(f"   زمان: {fastest['avg_total_ms']:.0f}ms")
        
        least_tokens = min(summary_data, key=lambda x: x['avg_tokens'])
        print(f"\n💰 کم‌ترین توکن: {least_tokens['provider']} - {least_tokens['model']}")
        print(f"   توکن: {least_tokens['avg_tokens']:.0f}")
        
        # توصیه
        print("\n" + "="*80)
        print("💡 توصیه")
        print("="*80)
        
        # محاسبه امتیاز (سرعت + کارایی توکن)
        for item in summary_data:
            # نرمال‌سازی (کمتر بهتر)
            speed_score = item['avg_total_ms'] / 1000  # به ثانیه
            token_score = item['avg_tokens'] / 1000  # نرمال‌سازی
            item['combined_score'] = speed_score + token_score
        
        best_overall = min(summary_data, key=lambda x: x['combined_score'])
        print(f"\n🎯 بهترین انتخاب کلی: {best_overall['provider']} - {best_overall['model']}")
        print(f"   زمان: {best_overall['avg_total_ms']:.0f}ms")
        print(f"   توکن: {best_overall['avg_tokens']:.0f}")
    
    # ذخیره گزارش
    report_file = '/tmp/benchmark_comparison_report.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            'summary': summary_data,
            'fastest': fastest if summary_data else None,
            'least_tokens': least_tokens if summary_data else None,
            'best_overall': best_overall if summary_data else None
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 گزارش کامل در {report_file} ذخیره شد")

def main():
    results = load_all_results()
    
    if not results:
        print("❌ هیچ فایل نتیجه‌ای یافت نشد!")
        print("ابتدا تست‌ها را اجرا کنید:")
        print("  bash /app/tests/run_comprehensive_benchmark.sh")
        return 1
    
    analyze_results(results)
    return 0

if __name__ == '__main__':
    exit(main())
