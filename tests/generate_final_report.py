#!/usr/bin/env python3
"""تولید گزارش نهایی از نتایج تست‌های LLM"""
import json
from pathlib import Path
from datetime import datetime

def load_results(filepath):
    """بارگذاری نتایج از فایل JSON"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_stats(results):
    """محاسبه آمار از نتایج"""
    stats = {}
    for key, data in results.items():
        successful = [r['result'] for r in data if r['result'].get('success', False)]
        failed = [r for r in data if not r['result'].get('success', False)]
        
        if successful:
            times = [r['time_ms'] for r in successful]
            tokens = [r.get('tokens', 0) for r in successful]
            
            stats[key] = {
                'total': len(data),
                'successful': len(successful),
                'failed': len(failed),
                'success_rate': (len(successful) / len(data)) * 100,
                'avg_time_ms': sum(times) / len(times),
                'min_time_ms': min(times),
                'max_time_ms': max(times),
                'avg_tokens': sum(tokens) / len(tokens) if tokens else 0,
                'total_tokens': sum(tokens),
                'all_results': data
            }
        else:
            stats[key] = {
                'total': len(data),
                'successful': 0,
                'failed': len(failed),
                'success_rate': 0,
                'avg_time_ms': 0,
                'min_time_ms': 0,
                'max_time_ms': 0,
                'avg_tokens': 0,
                'total_tokens': 0,
                'all_results': data
            }
    
    return stats

def generate_markdown_report(stage1_stats, stage2_stats, output_file):
    """تولید گزارش Markdown"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# گزارش جامع تست عملکرد مدل‌های LLM\n\n")
        f.write(f"**تاریخ تولید گزارش:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # خلاصه اجرایی
        f.write("## 📊 خلاصه اجرایی\n\n")
        f.write("این گزارش نتایج تست عملکرد مدل‌های مختلف LLM از دو منبع OpenAI و GapGPT را نشان می‌دهد.\n\n")
        
        # مرحله 1: کلاسیفیکیشن
        f.write("## 🎯 مرحله 1: تست کلاسیفیکیشن\n\n")
        f.write("**مدل‌ها:** `gpt-5-nano`, `gpt-4o-mini`\n\n")
        f.write("**تعداد سوالات:** 15 سوال برای هر مدل\n\n")
        
        f.write("### نتایج کلی\n\n")
        f.write("| مدل | منبع | موفق/کل | نرخ موفقیت | میانگین زمان | حداقل | حداکثر | میانگین توکن |\n")
        f.write("|-----|------|---------|------------|--------------|-------|-------|---------------|\n")
        
        for key in sorted(stage1_stats.keys()):
            stats = stage1_stats[key]
            provider, model = key.split('_', 1)
            f.write(f"| {model} | {provider} | {stats['successful']}/{stats['total']} | "
                   f"{stats['success_rate']:.1f}% | {stats['avg_time_ms']:.0f}ms | "
                   f"{stats['min_time_ms']:.0f}ms | {stats['max_time_ms']:.0f}ms | "
                   f"{stats['avg_tokens']:.0f} |\n")
        
        f.write("\n### تحلیل مرحله 1\n\n")
        
        # مقایسه gpt-5-nano
        if 'openai_gpt-5-nano' in stage1_stats and 'gapgpt_gpt-5-nano' in stage1_stats:
            openai_nano = stage1_stats['openai_gpt-5-nano']
            gapgpt_nano = stage1_stats['gapgpt_gpt-5-nano']
            
            f.write("#### مدل gpt-5-nano\n\n")
            if openai_nano['successful'] > 0 and gapgpt_nano['successful'] > 0:
                faster = 'OpenAI' if openai_nano['avg_time_ms'] < gapgpt_nano['avg_time_ms'] else 'GapGPT'
                diff = abs(openai_nano['avg_time_ms'] - gapgpt_nano['avg_time_ms'])
                f.write(f"- **سرعت:** {faster} با {diff:.0f}ms سریعتر است\n")
                f.write(f"- **نرخ موفقیت OpenAI:** {openai_nano['success_rate']:.1f}%\n")
                f.write(f"- **نرخ موفقیت GapGPT:** {gapgpt_nano['success_rate']:.1f}%\n")
            elif openai_nano['successful'] == 0:
                f.write("- ⚠️ **OpenAI gpt-5-nano:** همه تست‌ها ناموفق (مدل در دسترس نیست)\n")
            elif gapgpt_nano['successful'] == 0:
                f.write("- ⚠️ **GapGPT gpt-5-nano:** همه تست‌ها ناموفق\n")
            f.write("\n")
        
        # مقایسه gpt-4o-mini
        if 'openai_gpt-4o-mini' in stage1_stats and 'gapgpt_gpt-4o-mini' in stage1_stats:
            openai_mini = stage1_stats['openai_gpt-4o-mini']
            gapgpt_mini = stage1_stats['gapgpt_gpt-4o-mini']
            
            f.write("#### مدل gpt-4o-mini\n\n")
            if openai_mini['successful'] > 0 and gapgpt_mini['successful'] > 0:
                faster = 'OpenAI' if openai_mini['avg_time_ms'] < gapgpt_mini['avg_time_ms'] else 'GapGPT'
                diff = abs(openai_mini['avg_time_ms'] - gapgpt_mini['avg_time_ms'])
                f.write(f"- **سرعت:** {faster} با {diff:.0f}ms سریعتر است\n")
                f.write(f"- **نرخ موفقیت OpenAI:** {openai_mini['success_rate']:.1f}%\n")
                f.write(f"- **نرخ موفقیت GapGPT:** {gapgpt_mini['success_rate']:.1f}%\n")
            f.write("\n")
        
        # مرحله 2: سوالات عمومی
        f.write("## 🌍 مرحله 2: تست سوالات عمومی\n\n")
        f.write("**مدل‌ها:** `gpt-4o-mini`, `gpt-5-mini`, `gpt-5.1`, `gpt-5.2`\n\n")
        f.write("**تعداد سوالات:** 20 سوال برای هر مدل\n\n")
        
        f.write("### نتایج کلی\n\n")
        f.write("| مدل | منبع | موفق/کل | نرخ موفقیت | میانگین زمان | حداقل | حداکثر | میانگین توکن |\n")
        f.write("|-----|------|---------|------------|--------------|-------|-------|---------------|\n")
        
        for key in sorted(stage2_stats.keys()):
            stats = stage2_stats[key]
            provider, model = key.split('_', 1)
            f.write(f"| {model} | {provider} | {stats['successful']}/{stats['total']} | "
                   f"{stats['success_rate']:.1f}% | {stats['avg_time_ms']:.0f}ms | "
                   f"{stats['min_time_ms']:.0f}ms | {stats['max_time_ms']:.0f}ms | "
                   f"{stats['avg_tokens']:.0f} |\n")
        
        f.write("\n### تحلیل مرحله 2\n\n")
        
        # تحلیل هر مدل
        models = ['gpt-4o-mini', 'gpt-5-mini', 'gpt-5.1', 'gpt-5.2']
        for model in models:
            openai_key = f'openai_{model}'
            gapgpt_key = f'gapgpt_{model}'
            
            if openai_key in stage2_stats and gapgpt_key in stage2_stats:
                openai_stats = stage2_stats[openai_key]
                gapgpt_stats = stage2_stats[gapgpt_key]
                
                f.write(f"#### مدل {model}\n\n")
                
                if openai_stats['successful'] > 0 and gapgpt_stats['successful'] > 0:
                    faster = 'OpenAI' if openai_stats['avg_time_ms'] < gapgpt_stats['avg_time_ms'] else 'GapGPT'
                    diff = abs(openai_stats['avg_time_ms'] - gapgpt_stats['avg_time_ms'])
                    f.write(f"- **سرعت:** {faster} با {diff:.0f}ms سریعتر است\n")
                    f.write(f"- **نرخ موفقیت OpenAI:** {openai_stats['success_rate']:.1f}% ({openai_stats['successful']}/20)\n")
                    f.write(f"- **نرخ موفقیت GapGPT:** {gapgpt_stats['success_rate']:.1f}% ({gapgpt_stats['successful']}/20)\n")
                    f.write(f"- **میانگین توکن OpenAI:** {openai_stats['avg_tokens']:.0f}\n")
                    f.write(f"- **میانگین توکن GapGPT:** {gapgpt_stats['avg_tokens']:.0f}\n")
                    
                    if openai_stats['success_rate'] < 100 or gapgpt_stats['success_rate'] < 100:
                        f.write(f"- ⚠️ **مشکلات پایداری:** برخی درخواست‌ها با timeout یا خطا مواجه شدند\n")
                elif openai_stats['successful'] == 0:
                    f.write(f"- ❌ **OpenAI {model}:** همه تست‌ها ناموفق\n")
                elif gapgpt_stats['successful'] == 0:
                    f.write(f"- ❌ **GapGPT {model}:** همه تست‌ها ناموفق\n")
                
                f.write("\n")
        
        # توصیه‌ها
        f.write("## 💡 توصیه‌ها\n\n")
        f.write("### برای کلاسیفیکیشن\n\n")
        
        # پیدا کردن بهترین مدل برای کلاسیفیکیشن
        best_classification = None
        best_score = 0
        
        for key, stats in stage1_stats.items():
            if stats['successful'] > 0:
                # امتیاز = نرخ موفقیت - (زمان / 1000)
                score = stats['success_rate'] - (stats['avg_time_ms'] / 100)
                if score > best_score:
                    best_score = score
                    best_classification = key
        
        if best_classification:
            provider, model = best_classification.split('_', 1)
            stats = stage1_stats[best_classification]
            f.write(f"**بهترین گزینه:** `{model}` از منبع `{provider}`\n\n")
            f.write(f"- نرخ موفقیت: {stats['success_rate']:.1f}%\n")
            f.write(f"- میانگین زمان: {stats['avg_time_ms']:.0f}ms\n")
            f.write(f"- میانگین توکن: {stats['avg_tokens']:.0f}\n\n")
        
        f.write("### برای سوالات عمومی\n\n")
        
        # پیدا کردن بهترین مدل برای سوالات عمومی
        best_general = None
        best_score = 0
        
        for key, stats in stage2_stats.items():
            if stats['successful'] > 0:
                # امتیاز = نرخ موفقیت - (زمان / 1000)
                score = stats['success_rate'] - (stats['avg_time_ms'] / 100)
                if score > best_score:
                    best_score = score
                    best_general = key
        
        if best_general:
            provider, model = best_general.split('_', 1)
            stats = stage2_stats[best_general]
            f.write(f"**بهترین گزینه:** `{model}` از منبع `{provider}`\n\n")
            f.write(f"- نرخ موفقیت: {stats['success_rate']:.1f}%\n")
            f.write(f"- میانگین زمان: {stats['avg_time_ms']:.0f}ms\n")
            f.write(f"- میانگین توکن: {stats['avg_tokens']:.0f}\n\n")
        
        f.write("### مقایسه OpenAI vs GapGPT\n\n")
        
        # محاسبه میانگین کلی
        openai_times = []
        gapgpt_times = []
        openai_success = []
        gapgpt_success = []
        
        for key, stats in {**stage1_stats, **stage2_stats}.items():
            if stats['successful'] > 0:
                if key.startswith('openai_'):
                    openai_times.append(stats['avg_time_ms'])
                    openai_success.append(stats['success_rate'])
                elif key.startswith('gapgpt_'):
                    gapgpt_times.append(stats['avg_time_ms'])
                    gapgpt_success.append(stats['success_rate'])
        
        if openai_times and gapgpt_times:
            avg_openai_time = sum(openai_times) / len(openai_times)
            avg_gapgpt_time = sum(gapgpt_times) / len(gapgpt_times)
            avg_openai_success = sum(openai_success) / len(openai_success)
            avg_gapgpt_success = sum(gapgpt_success) / len(gapgpt_success)
            
            f.write(f"- **میانگین زمان OpenAI:** {avg_openai_time:.0f}ms\n")
            f.write(f"- **میانگین زمان GapGPT:** {avg_gapgpt_time:.0f}ms\n")
            f.write(f"- **میانگین نرخ موفقیت OpenAI:** {avg_openai_success:.1f}%\n")
            f.write(f"- **میانگین نرخ موفقیت GapGPT:** {avg_gapgpt_success:.1f}%\n\n")
            
            if avg_openai_time < avg_gapgpt_time:
                diff_pct = ((avg_gapgpt_time - avg_openai_time) / avg_openai_time) * 100
                f.write(f"✅ **OpenAI به طور متوسط {diff_pct:.1f}% سریعتر است**\n\n")
            else:
                diff_pct = ((avg_openai_time - avg_gapgpt_time) / avg_gapgpt_time) * 100
                f.write(f"✅ **GapGPT به طور متوسط {diff_pct:.1f}% سریعتر است**\n\n")
        
        # مشکلات شناسایی شده
        f.write("## ⚠️ مشکلات شناسایی شده\n\n")
        
        problematic_models = []
        for key, stats in {**stage1_stats, **stage2_stats}.items():
            if stats['success_rate'] < 100:
                provider, model = key.split('_', 1)
                failed_count = stats['failed']
                problematic_models.append((model, provider, stats['success_rate'], failed_count))
        
        if problematic_models:
            f.write("### مدل‌های با مشکل پایداری\n\n")
            for model, provider, success_rate, failed_count in problematic_models:
                f.write(f"- **{model}** ({provider}): {failed_count} درخواست ناموفق (نرخ موفقیت: {success_rate:.1f}%)\n")
            
            f.write("\n**دلایل احتمالی:**\n")
            f.write("- Timeout در برقراری ارتباط\n")
            f.write("- مشکلات شبکه یا SSL\n")
            f.write("- عدم دسترسی به مدل خاص\n")
            f.write("- محدودیت rate limit\n\n")
        else:
            f.write("✅ همه مدل‌ها با نرخ موفقیت 100% کار کردند\n\n")
        
        # پیوست: نمونه پاسخ‌ها
        f.write("## 📎 پیوست: نمونه پاسخ‌ها\n\n")
        f.write("### مرحله 1: کلاسیفیکیشن\n\n")
        
        for key in sorted(stage1_stats.keys()):
            stats = stage1_stats[key]
            if stats['successful'] > 0:
                provider, model = key.split('_', 1)
                f.write(f"#### {model} ({provider})\n\n")
                
                # نمایش 3 نمونه اول
                for i, item in enumerate(stats['all_results'][:3]):
                    query = item['query']
                    result = item['result']
                    if result.get('success'):
                        answer = result.get('answer', 'N/A')
                        time_ms = result.get('time_ms', 0)
                        f.write(f"**سوال {i+1}:** {query}\n\n")
                        f.write(f"**پاسخ:** {answer[:200]}{'...' if len(answer) > 200 else ''}\n\n")
                        f.write(f"**زمان:** {time_ms:.0f}ms\n\n")
                        f.write("---\n\n")
        
        f.write("### مرحله 2: سوالات عمومی\n\n")
        
        for key in sorted(stage2_stats.keys()):
            stats = stage2_stats[key]
            if stats['successful'] > 0:
                provider, model = key.split('_', 1)
                f.write(f"#### {model} ({provider})\n\n")
                
                # نمایش 2 نمونه اول
                shown = 0
                for item in stats['all_results']:
                    if shown >= 2:
                        break
                    query = item['query']
                    result = item['result']
                    if result.get('success'):
                        answer = result.get('answer', 'N/A')
                        time_ms = result.get('time_ms', 0)
                        tokens = result.get('tokens', 0)
                        f.write(f"**سوال:** {query}\n\n")
                        f.write(f"**پاسخ:** {answer[:300]}{'...' if len(answer) > 300 else ''}\n\n")
                        f.write(f"**زمان:** {time_ms:.0f}ms | **توکن:** {tokens}\n\n")
                        f.write("---\n\n")
                        shown += 1
        
        f.write("\n## 🎯 نتیجه‌گیری نهایی\n\n")
        f.write("بر اساس نتایج تست‌ها:\n\n")
        f.write("1. **برای کلاسیفیکیشن:** استفاده از مدل‌های سبک و سریع مانند `gpt-4o-mini` توصیه می‌شود\n")
        f.write("2. **برای سوالات عمومی:** مدل‌های `gpt-5.1` یا `gpt-4o-mini` بهترین تعادل بین سرعت و کیفیت را دارند\n")
        f.write("3. **انتخاب منبع:** بسته به نیاز به سرعت یا پایداری، می‌توان بین OpenAI و GapGPT انتخاب کرد\n")
        f.write("4. **نکته مهم:** برخی مدل‌ها (مانند `gpt-5-nano`, `gpt-5-mini`, `gpt-5.2`) مشکلات پایداری دارند و برای استفاده production توصیه نمی‌شوند\n\n")
        
        f.write("---\n\n")
        f.write("*این گزارش به صورت خودکار تولید شده است*\n")

def main():
    # بارگذاری نتایج
    stage1_results = load_results('/srv/test_results_stage1_classification.json')
    stage2_results = load_results('/srv/test_results_stage2_general.json')
    
    # محاسبه آمار
    stage1_stats = calculate_stats(stage1_results)
    stage2_stats = calculate_stats(stage2_results)
    
    # تولید گزارش
    output_file = '/srv/LLM_Performance_Report.md'
    generate_markdown_report(stage1_stats, stage2_stats, output_file)
    
    print(f"✅ گزارش نهایی در {output_file} ذخیره شد")
    
    # نمایش خلاصه
    print("\n" + "=" * 70)
    print("📊 خلاصه نتایج")
    print("=" * 70)
    
    print("\n🎯 مرحله 1: کلاسیفیکیشن")
    for key in sorted(stage1_stats.keys()):
        stats = stage1_stats[key]
        print(f"  {key:30s}: {stats['successful']}/{stats['total']} موفق | "
              f"{stats['avg_time_ms']:6.0f}ms | {stats['avg_tokens']:4.0f} توکن")
    
    print("\n🌍 مرحله 2: سوالات عمومی")
    for key in sorted(stage2_stats.keys()):
        stats = stage2_stats[key]
        print(f"  {key:30s}: {stats['successful']}/{stats['total']} موفق | "
              f"{stats['avg_time_ms']:6.0f}ms | {stats['avg_tokens']:4.0f} توکن")
    
    print("\n" + "=" * 70)

if __name__ == '__main__':
    main()
