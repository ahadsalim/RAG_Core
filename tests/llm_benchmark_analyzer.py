#!/usr/bin/env python3
"""
تحلیلگر نتایج تست LLM
خواندن فایل‌های نتایج و تولید گزارش‌های تحلیلی
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import argparse


class LLMBenchmarkAnalyzer:
    """کلاس تحلیل نتایج benchmark"""
    
    def __init__(self, results_dir: str = "benchmark_results"):
        self.results_dir = Path(results_dir)
        self.results = []
        self.summary = {}
        
    def load_results(self, result_file: str = None):
        """بارگذاری نتایج از فایل"""
        
        if result_file:
            file_path = Path(result_file)
        else:
            result_files = sorted(self.results_dir.glob("results_*.json"))
            if not result_files:
                print("❌ No result files found!")
                return False
            file_path = result_files[-1]
        
        print(f"📂 Loading results from: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.results = data.get('results', [])
            self.config = data.get('config', 'unknown')
            self.llm_type = data.get('llm_type', 'unknown')
            self.timestamp = data.get('timestamp', 'unknown')
        
        print(f"✅ Loaded {len(self.results)} test results")
        return True
    
    def load_summary(self, summary_file: str = None):
        """بارگذاری خلاصه نتایج"""
        
        if summary_file:
            file_path = Path(summary_file)
        else:
            summary_files = sorted(self.results_dir.glob("summary_*.json"))
            if not summary_files:
                print("❌ No summary files found!")
                return False
            file_path = summary_files[-1]
        
        print(f"📂 Loading summary from: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.summary = data.get('summary', {})
        
        print(f"✅ Loaded summary for {len(self.summary)} configurations")
        return True
    
    def analyze_by_provider(self) -> Dict[str, Any]:
        """تحلیل بر اساس provider"""
        
        provider_stats = {}
        
        for result in self.results:
            provider = result['provider']
            
            if provider not in provider_stats:
                provider_stats[provider] = {
                    'total': 0,
                    'success': 0,
                    'failed': 0,
                    'times': [],
                    'tokens': []
                }
            
            provider_stats[provider]['total'] += 1
            
            if result['success']:
                provider_stats[provider]['success'] += 1
                provider_stats[provider]['times'].append(result['time_ms'])
                provider_stats[provider]['tokens'].append(result.get('total_tokens', 0))
            else:
                provider_stats[provider]['failed'] += 1
        
        for provider, stats in provider_stats.items():
            if stats['times']:
                stats['avg_time_ms'] = int(sum(stats['times']) / len(stats['times']))
                stats['min_time_ms'] = min(stats['times'])
                stats['max_time_ms'] = max(stats['times'])
                stats['avg_tokens'] = int(sum(stats['tokens']) / len(stats['tokens']))
                stats['success_rate'] = stats['success'] / stats['total']
            
            del stats['times']
            del stats['tokens']
        
        return provider_stats
    
    def analyze_by_model(self) -> Dict[str, Any]:
        """تحلیل بر اساس model"""
        
        model_stats = {}
        
        for result in self.results:
            key = f"{result['provider']}/{result['model']}"
            
            if key not in model_stats:
                model_stats[key] = {
                    'provider': result['provider'],
                    'model': result['model'],
                    'total': 0,
                    'success': 0,
                    'failed': 0,
                    'times': [],
                    'tokens': []
                }
            
            model_stats[key]['total'] += 1
            
            if result['success']:
                model_stats[key]['success'] += 1
                model_stats[key]['times'].append(result['time_ms'])
                model_stats[key]['tokens'].append(result.get('total_tokens', 0))
            else:
                model_stats[key]['failed'] += 1
        
        for key, stats in model_stats.items():
            if stats['times']:
                stats['avg_time_ms'] = int(sum(stats['times']) / len(stats['times']))
                stats['min_time_ms'] = min(stats['times'])
                stats['max_time_ms'] = max(stats['times'])
                stats['avg_tokens'] = int(sum(stats['tokens']) / len(stats['tokens']))
                stats['success_rate'] = stats['success'] / stats['total']
            
            del stats['times']
            del stats['tokens']
        
        return model_stats
    
    def analyze_by_category(self) -> Dict[str, Any]:
        """تحلیل بر اساس دسته‌بندی سوالات"""
        
        category_stats = {}
        
        for result in self.results:
            category = result.get('category', 'unknown')
            
            if category not in category_stats:
                category_stats[category] = {
                    'total': 0,
                    'success': 0,
                    'failed': 0,
                    'times': [],
                    'tokens': []
                }
            
            category_stats[category]['total'] += 1
            
            if result['success']:
                category_stats[category]['success'] += 1
                category_stats[category]['times'].append(result['time_ms'])
                category_stats[category]['tokens'].append(result.get('total_tokens', 0))
            else:
                category_stats[category]['failed'] += 1
        
        for category, stats in category_stats.items():
            if stats['times']:
                stats['avg_time_ms'] = int(sum(stats['times']) / len(stats['times']))
                stats['avg_tokens'] = int(sum(stats['tokens']) / len(stats['tokens']))
                stats['success_rate'] = stats['success'] / stats['total']
            
            del stats['times']
            del stats['tokens']
        
        return category_stats
    
    def generate_markdown_report(self, output_file: str = None):
        """تولید گزارش Markdown"""
        
        if not output_file:
            output_file = self.results_dir / f"report_{self.timestamp}.md"
        
        provider_stats = self.analyze_by_provider()
        model_stats = self.analyze_by_model()
        category_stats = self.analyze_by_category()
        
        report = []
        report.append(f"# گزارش تست LLM - {self.timestamp}\n")
        report.append(f"**تنظیمات:** {self.config}\n")
        report.append(f"**نوع LLM:** {self.llm_type}\n")
        report.append(f"**تعداد کل تست‌ها:** {len(self.results)}\n")
        report.append(f"**تاریخ:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        report.append("\n---\n")
        report.append("\n## 📊 خلاصه نتایج بر اساس Provider\n")
        report.append("\n| Provider | تعداد | موفق | ناموفق | میانگین زمان | میانگین توکن | نرخ موفقیت |\n")
        report.append("|----------|-------|------|--------|--------------|--------------|------------|\n")
        
        for provider, stats in sorted(provider_stats.items()):
            report.append(
                f"| {provider} | {stats['total']} | {stats['success']} | {stats['failed']} | "
                f"{stats.get('avg_time_ms', 0)}ms | {stats.get('avg_tokens', 0)} | "
                f"{stats.get('success_rate', 0)*100:.1f}% |\n"
            )
        
        report.append("\n---\n")
        report.append("\n## 🎯 نتایج تفصیلی بر اساس Model\n")
        report.append("\n| Provider/Model | تعداد | موفق | میانگین زمان | Min | Max | میانگین توکن | نرخ موفقیت |\n")
        report.append("|----------------|-------|------|--------------|-----|-----|--------------|------------|\n")
        
        sorted_models = sorted(model_stats.items(), key=lambda x: x[1].get('avg_time_ms', 0))
        
        for key, stats in sorted_models:
            report.append(
                f"| {key} | {stats['total']} | {stats['success']} | "
                f"{stats.get('avg_time_ms', 0)}ms | {stats.get('min_time_ms', 0)}ms | "
                f"{stats.get('max_time_ms', 0)}ms | {stats.get('avg_tokens', 0)} | "
                f"{stats.get('success_rate', 0)*100:.1f}% |\n"
            )
        
        report.append("\n---\n")
        report.append("\n## 📂 تحلیل بر اساس دسته‌بندی سوالات\n")
        report.append("\n| دسته‌بندی | تعداد | موفق | میانگین زمان | میانگین توکن | نرخ موفقیت |\n")
        report.append("|----------|-------|------|--------------|--------------|------------|\n")
        
        for category, stats in sorted(category_stats.items()):
            report.append(
                f"| {category} | {stats['total']} | {stats['success']} | "
                f"{stats.get('avg_time_ms', 0)}ms | {stats.get('avg_tokens', 0)} | "
                f"{stats.get('success_rate', 0)*100:.1f}% |\n"
            )
        
        report.append("\n---\n")
        report.append("\n## 🏆 توصیه‌ها\n\n")
        
        if sorted_models:
            fastest = sorted_models[0]
            report.append(f"### سریع‌ترین مدل\n")
            report.append(f"- **{fastest[0]}**: {fastest[1].get('avg_time_ms', 0)}ms میانگین زمان\n\n")
        
        most_efficient = sorted(
            [(k, v) for k, v in model_stats.items() if v.get('success_rate', 0) == 1.0],
            key=lambda x: x[1].get('avg_tokens', 0)
        )
        
        if most_efficient:
            report.append(f"### کارآمدترین مدل (کمترین توکن با 100% موفقیت)\n")
            report.append(f"- **{most_efficient[0][0]}**: {most_efficient[0][1].get('avg_tokens', 0)} توکن میانگین\n\n")
        
        report.append("\n---\n")
        report.append("\n## 📝 نمونه پاسخ‌ها\n\n")
        
        for i, result in enumerate(self.results[:3], 1):
            if result['success']:
                report.append(f"### نمونه {i}: {result.get('category', 'unknown')}\n\n")
                report.append(f"**Provider/Model:** {result['provider']}/{result['model']}\n\n")
                report.append(f"**سوال:** {result['query']}\n\n")
                report.append(f"**پاسخ:**\n```\n{result['answer'][:500]}...\n```\n\n")
                report.append(f"**زمان:** {result['time_ms']}ms | **توکن:** {result.get('total_tokens', 0)}\n\n")
                report.append("---\n\n")
        
        report_content = "".join(report)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"\n✅ Report generated: {output_file}")
        
        return output_file
    
    def print_summary_table(self):
        """چاپ جدول خلاصه"""
        
        if not self.summary:
            print("⚠️  No summary loaded. Load summary first.")
            return
        
        print(f"\n{'='*100}")
        print(f"📊 SUMMARY TABLE")
        print(f"{'='*100}\n")
        
        print(f"{'Provider/Model':<35} {'Tests':<8} {'Success':<10} {'Avg Time':<12} {'Tokens':<10} {'Rate':<8}")
        print(f"{'-'*100}")
        
        sorted_summary = sorted(
            self.summary.items(),
            key=lambda x: x[1].get('avg_time_ms', 0)
        )
        
        for key, data in sorted_summary:
            tests_str = f"{data['total_queries']}"
            success_str = f"{data['successful']}/{data['total_queries']}"
            time_str = f"{data.get('avg_time_ms', 0)}ms"
            tokens_str = f"{data.get('avg_tokens', 0)}"
            rate_str = f"{data.get('success_rate', 0)*100:.1f}%"
            
            print(f"{key:<35} {tests_str:<8} {success_str:<10} {time_str:<12} {tokens_str:<10} {rate_str:<8}")
        
        print(f"\n{'='*100}\n")


def main():
    parser = argparse.ArgumentParser(description='LLM Benchmark Results Analyzer')
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='benchmark_results',
        help='Directory containing benchmark results'
    )
    
    parser.add_argument(
        '--result-file',
        type=str,
        help='Specific result file to analyze'
    )
    
    parser.add_argument(
        '--summary-file',
        type=str,
        help='Specific summary file to load'
    )
    
    parser.add_argument(
        '--generate-report',
        action='store_true',
        help='Generate markdown report'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for markdown report'
    )
    
    args = parser.parse_args()
    
    analyzer = LLMBenchmarkAnalyzer(results_dir=args.results_dir)
    
    if args.result_file or not args.summary_file:
        if not analyzer.load_results(args.result_file):
            return
    
    if args.summary_file or not args.result_file:
        if not analyzer.load_summary(args.summary_file):
            if not args.result_file:
                return
    
    if args.generate_report and analyzer.results:
        analyzer.generate_markdown_report(args.output)
    
    if analyzer.summary:
        analyzer.print_summary_table()


if __name__ == "__main__":
    main()
