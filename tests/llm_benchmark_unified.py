#!/usr/bin/env python3
"""
سیستم تست جامع و یکپارچه LLM
قابلیت تست تمام ترکیبات: providers × models × query_types
با ذخیره نتایج و تحلیل کامل
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import argparse

sys.path.append(str(Path(__file__).parent.parent))

from app.llm.factory import LLMWithFallback
from app.llm.models import LLMConfig, Message
from llm_test_config import (
    PROVIDERS, LLM_TYPES, TEST_QUERIES, TEST_CONFIGS,
    get_provider_config, get_llm_type_config, get_test_config,
    list_available_models, get_recommended_model
)


class LLMBenchmarkUnified:
    """کلاس اصلی برای تست جامع LLM ها"""
    
    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results = []
        self.summary = {}
        
    def _get_api_key(self, env_var: str) -> str:
        """دریافت API key از environment"""
        api_key = os.getenv(env_var, "")
        if not api_key:
            print(f"⚠️  Warning: {env_var} not found in environment")
        return api_key
    
    async def test_single_query(
        self,
        provider_key: str,
        model: str,
        query: str,
        llm_type: str = "llm2",
        query_id: str = None,
        category: str = None
    ) -> Dict[str, Any]:
        """تست یک سوال با یک مدل خاص"""
        
        provider_config = get_provider_config(provider_key)
        llm_config_data = get_llm_type_config(llm_type)
        
        if not provider_config or not llm_config_data:
            return {
                'error': 'Invalid provider or llm_type',
                'provider': provider_key,
                'model': model
            }
        
        api_key = self._get_api_key(provider_config['api_key_env'])
        
        llm_config = LLMConfig(
            provider=provider_config['name'],
            model=model,
            api_key=api_key,
            base_url=provider_config['base_url'],
            max_tokens=llm_config_data['max_tokens'],
            temperature=llm_config_data['temperature']
        )
        
        llm = LLMWithFallback(primary_config=llm_config, fallback_config=None)
        
        messages = [Message(role="user", content=query)]
        
        start_time = time.time()
        
        try:
            response = await llm.generate(messages)
            end_time = time.time()
            
            result = {
                'query_id': query_id,
                'category': category,
                'provider': provider_key,
                'model': model,
                'llm_type': llm_type,
                'query': query,
                'answer': response.content,
                'success': True,
                'time_ms': int((end_time - start_time) * 1000),
                'input_tokens': response.usage.get('prompt_tokens', 0),
                'output_tokens': response.usage.get('completion_tokens', 0),
                'total_tokens': response.usage.get('total_tokens', 0),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            end_time = time.time()
            result = {
                'query_id': query_id,
                'category': category,
                'provider': provider_key,
                'model': model,
                'llm_type': llm_type,
                'query': query,
                'answer': None,
                'success': False,
                'error': str(e),
                'time_ms': int((end_time - start_time) * 1000),
                'timestamp': datetime.now().isoformat()
            }
        
        return result
    
    async def test_provider_model_combination(
        self,
        provider_key: str,
        model: str,
        queries: List[Dict],
        llm_type: str = "llm2"
    ) -> List[Dict]:
        """تست یک ترکیب provider + model با لیست سوالات"""
        
        print(f"\n{'='*80}")
        print(f"🧪 Testing: {provider_key}/{model} ({llm_type})")
        print(f"{'='*80}")
        
        results = []
        
        for i, query_data in enumerate(queries, 1):
            query = query_data.get('query', '')
            query_id = query_data.get('id', f'q_{i}')
            category = query_data.get('category', 'unknown')
            
            print(f"\n[{i}/{len(queries)}] Query: {query[:60]}...")
            
            result = await self.test_single_query(
                provider_key=provider_key,
                model=model,
                query=query,
                llm_type=llm_type,
                query_id=query_id,
                category=category
            )
            
            results.append(result)
            
            if result['success']:
                print(f"  ✅ Success | Time: {result['time_ms']}ms | Tokens: {result['total_tokens']}")
            else:
                print(f"  ❌ Failed | Error: {result.get('error', 'Unknown')}")
            
            await asyncio.sleep(0.5)
        
        return results
    
    async def run_test_config(
        self,
        config_name: str = "standard",
        providers: List[str] = None,
        models: List[str] = None,
        llm_type: str = "llm2"
    ):
        """اجرای یک تست با تنظیمات مشخص"""
        
        config = get_test_config(config_name)
        
        print(f"\n{'#'*80}")
        print(f"# 🚀 Starting Benchmark: {config['name']}")
        print(f"# {config['description']}")
        print(f"# LLM Type: {llm_type}")
        print(f"{'#'*80}\n")
        
        test_providers = providers or config.get('providers', ['gapgpt'])
        
        all_results = []
        
        for provider_key in test_providers:
            provider_config = get_provider_config(provider_key)
            if not provider_config:
                print(f"⚠️  Provider '{provider_key}' not found, skipping...")
                continue
            
            available_models = provider_config.get('models', [])
            
            if models:
                test_models = [m for m in models if m in available_models]
            else:
                models_limit = config.get('models_per_provider')
                test_models = available_models[:models_limit] if models_limit else available_models
            
            for model in test_models:
                for query_category, queries in config['queries'].items():
                    if not queries:
                        continue
                    
                    results = await self.test_provider_model_combination(
                        provider_key=provider_key,
                        model=model,
                        queries=queries,
                        llm_type=llm_type
                    )
                    
                    all_results.extend(results)
        
        self.results = all_results
        self._generate_summary()
        self._save_results(config_name, llm_type)
        
        return all_results
    
    def _generate_summary(self):
        """تولید خلاصه نتایج"""
        
        summary = {}
        
        for result in self.results:
            provider = result['provider']
            model = result['model']
            key = f"{provider}/{model}"
            
            if key not in summary:
                summary[key] = {
                    'provider': provider,
                    'model': model,
                    'total_queries': 0,
                    'successful': 0,
                    'failed': 0,
                    'total_time_ms': 0,
                    'total_tokens': 0,
                    'times': [],
                    'tokens': []
                }
            
            summary[key]['total_queries'] += 1
            
            if result['success']:
                summary[key]['successful'] += 1
                summary[key]['total_time_ms'] += result['time_ms']
                summary[key]['total_tokens'] += result.get('total_tokens', 0)
                summary[key]['times'].append(result['time_ms'])
                summary[key]['tokens'].append(result.get('total_tokens', 0))
            else:
                summary[key]['failed'] += 1
        
        for key, data in summary.items():
            if data['successful'] > 0:
                data['avg_time_ms'] = int(data['total_time_ms'] / data['successful'])
                data['avg_tokens'] = int(data['total_tokens'] / data['successful'])
                data['min_time_ms'] = min(data['times'])
                data['max_time_ms'] = max(data['times'])
                data['success_rate'] = data['successful'] / data['total_queries']
            else:
                data['avg_time_ms'] = 0
                data['avg_tokens'] = 0
                data['min_time_ms'] = 0
                data['max_time_ms'] = 0
                data['success_rate'] = 0.0
            
            del data['times']
            del data['tokens']
        
        self.summary = summary
    
    def _save_results(self, config_name: str, llm_type: str):
        """ذخیره نتایج در فایل"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        results_file = self.output_dir / f"results_{config_name}_{llm_type}_{timestamp}.json"
        summary_file = self.output_dir / f"summary_{config_name}_{llm_type}_{timestamp}.json"
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'config': config_name,
                'llm_type': llm_type,
                'timestamp': timestamp,
                'total_tests': len(self.results),
                'results': self.results
            }, f, ensure_ascii=False, indent=2)
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'config': config_name,
                'llm_type': llm_type,
                'timestamp': timestamp,
                'summary': self.summary
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*80}")
        print(f"💾 Results saved:")
        print(f"   - {results_file}")
        print(f"   - {summary_file}")
        print(f"{'='*80}\n")
    
    def print_summary(self):
        """چاپ خلاصه نتایج"""
        
        print(f"\n{'#'*80}")
        print(f"# 📊 BENCHMARK SUMMARY")
        print(f"{'#'*80}\n")
        
        sorted_summary = sorted(
            self.summary.items(),
            key=lambda x: x[1]['avg_time_ms']
        )
        
        print(f"{'Provider/Model':<30} {'Success':<10} {'Avg Time':<12} {'Avg Tokens':<12} {'Rate':<8}")
        print(f"{'-'*80}")
        
        for key, data in sorted_summary:
            success_str = f"{data['successful']}/{data['total_queries']}"
            time_str = f"{data['avg_time_ms']}ms"
            tokens_str = f"{data['avg_tokens']}"
            rate_str = f"{data['success_rate']*100:.1f}%"
            
            print(f"{key:<30} {success_str:<10} {time_str:<12} {tokens_str:<12} {rate_str:<8}")
        
        print(f"\n{'='*80}\n")


async def main():
    parser = argparse.ArgumentParser(description='LLM Unified Benchmark System')
    
    parser.add_argument(
        '--config',
        type=str,
        default='standard',
        choices=['quick', 'standard', 'comprehensive', 'quality', 'timing'],
        help='Test configuration to use'
    )
    
    parser.add_argument(
        '--llm-type',
        type=str,
        default='llm2',
        choices=['classification', 'llm1', 'llm2'],
        help='LLM type to test'
    )
    
    parser.add_argument(
        '--providers',
        type=str,
        nargs='+',
        help='Specific providers to test (e.g., gapgpt openai)'
    )
    
    parser.add_argument(
        '--models',
        type=str,
        nargs='+',
        help='Specific models to test (e.g., gpt-4o-mini gpt-5-mini)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='benchmark_results',
        help='Output directory for results'
    )
    
    parser.add_argument(
        '--list-models',
        action='store_true',
        help='List available models and exit'
    )
    
    args = parser.parse_args()
    
    if args.list_models:
        print("\n📋 Available Models:\n")
        models = list_available_models()
        for provider, model_list in models.items():
            print(f"  {provider}:")
            for model in model_list:
                recommended = ""
                for llm_type in ['classification', 'llm1', 'llm2']:
                    if model == get_recommended_model(llm_type, provider):
                        recommended = f" ⭐ (recommended for {llm_type})"
                        break
                print(f"    - {model}{recommended}")
            print()
        return
    
    benchmark = LLMBenchmarkUnified(output_dir=args.output_dir)
    
    await benchmark.run_test_config(
        config_name=args.config,
        providers=args.providers,
        models=args.models,
        llm_type=args.llm_type
    )
    
    benchmark.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
