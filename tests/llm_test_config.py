#!/usr/bin/env python3
"""
تنظیمات مرکزی برای تست LLM ها
شامل تعریف providers، models، و سوالات تست
"""

# =============================================================================
# LLM Providers Configuration
# =============================================================================

PROVIDERS = {
    'gapgpt': {
        'name': 'GapGPT',
        'base_url': 'https://api.gapgpt.app/v1',
        'api_key_env': 'LLM1_API_KEY',  # از .env خوانده می‌شود
        'models': [
            'gpt-4o-mini',
            'gpt-5-mini',
            'gpt-5.1',
            'gpt-5.2-chat-latest',
        ]
    },
    'openai': {
        'name': 'OpenAI',
        'base_url': 'https://api.openai.com/v1',
        'api_key_env': 'LLM1_FALLBACK_API_KEY',
        'models': [
            'gpt-4o-mini',
            'gpt-4o',
            'gpt-4-turbo',
        ]
    }
}

# =============================================================================
# LLM Types Configuration
# =============================================================================

LLM_TYPES = {
    'classification': {
        'name': 'Classification',
        'description': 'دسته‌بندی سوالات',
        'max_tokens': 512,
        'temperature': 0.2,
        'recommended_models': {
            'gapgpt': 'gpt-4o-mini',
            'openai': 'gpt-4o-mini'
        }
    },
    'llm1': {
        'name': 'LLM1 (Light)',
        'description': 'سوالات عمومی و نامعتبر',
        'max_tokens': 2048,
        'temperature': 0.7,
        'recommended_models': {
            'gapgpt': 'gpt-4o-mini',
            'openai': 'gpt-4o-mini'
        }
    },
    'llm2': {
        'name': 'LLM2 (Pro)',
        'description': 'سوالات تجاری و تخصصی',
        'max_tokens': 8192,
        'temperature': 0.4,
        'recommended_models': {
            'gapgpt': 'gpt-5-mini',
            'openai': 'gpt-4o'
        }
    }
}

# =============================================================================
# Test Queries by Category
# =============================================================================

TEST_QUERIES = {
    'classification': [
        {
            'id': 'cls_1',
            'query': 'سلام',
            'expected_category': 'invalid_no_file',
            'description': 'سوال نامعتبر ساده'
        },
        {
            'id': 'cls_2',
            'query': 'مالیات بر ارزش افزوده چیست؟',
            'expected_category': 'business_no_file',
            'description': 'سوال تجاری ساده'
        },
        {
            'id': 'cls_3',
            'query': 'آب و هوای امروز چطور است؟',
            'expected_category': 'general',
            'description': 'سوال عمومی'
        },
    ],
    
    'general': [
        {
            'id': 'gen_1',
            'category': 'سلام و احوالپرسی',
            'query': 'سلام، حالت چطوره؟'
        },
        {
            'id': 'gen_2',
            'category': 'سوال عمومی',
            'query': 'پایتخت ایران کجاست؟'
        },
        {
            'id': 'gen_3',
            'category': 'درخواست نامعتبر',
            'query': 'یک شعر برایم بگو'
        },
    ],
    
    'business_simple': [
        {
            'id': 'biz_s1',
            'category': 'مالیات - ساده',
            'query': 'نرخ مالیات بر ارزش افزوده در ایران چقدر است؟'
        },
        {
            'id': 'biz_s2',
            'category': 'بیمه - ساده',
            'query': 'نرخ حق بیمه تامین اجتماعی چقدر است؟'
        },
        {
            'id': 'biz_s3',
            'category': 'گمرک - ساده',
            'query': 'تعرفه گمرکی چیست؟'
        },
    ],
    
    'business_complex': [
        {
            'id': 'biz_c1',
            'category': 'مالیات - پیچیده',
            'query': 'یک شرکت تولیدی با درآمد سالانه 5 میلیارد تومان چه مالیات‌هایی باید بپردازد و چگونه محاسبه می‌شود؟'
        },
        {
            'id': 'biz_c2',
            'category': 'بیمه - کاربردی',
            'query': 'یک کارگر با حقوق 10 میلیون تومان چقدر حق بیمه باید بپردازد و سهم کارفرما چقدر است؟'
        },
        {
            'id': 'biz_c3',
            'category': 'گمرک - تخصصی',
            'query': 'برای واردات یک دستگاه صنعتی به ارزش 50000 دلار چه مراحل گمرکی و چه هزینه‌هایی باید پرداخت شود؟'
        },
        {
            'id': 'biz_c4',
            'category': 'ترکیبی - مشاوره‌ای',
            'query': 'یک فریلنسر که از خارج درآمد دارد چه تکالیف مالیاتی و بیمه‌ای دارد؟'
        },
    ],
    
    'business_timing': [
        {
            'id': 'time_1',
            'category': 'مالیات',
            'query': 'مالیات بر ارزش افزوده چیست و چگونه محاسبه می‌شود؟'
        },
        {
            'id': 'time_2',
            'category': 'بیمه',
            'query': 'حق بیمه تامین اجتماعی چگونه محاسبه می‌شود؟'
        },
        {
            'id': 'time_3',
            'category': 'گمرک',
            'query': 'تعرفه گمرکی چیست و چگونه تعیین می‌شود؟'
        },
        {
            'id': 'time_4',
            'category': 'مالیات',
            'query': 'نرخ مالیات بر درآمد اشخاص حقیقی چقدر است؟'
        },
        {
            'id': 'time_5',
            'category': 'بیمه',
            'query': 'سهم کارفرما و کارگر از حق بیمه چقدر است؟'
        },
    ]
}

# =============================================================================
# Test Configurations
# =============================================================================

TEST_CONFIGS = {
    'quick': {
        'name': 'تست سریع',
        'description': 'تست سریع با تعداد محدود سوال',
        'queries': {
            'classification': TEST_QUERIES['classification'][:2],
            'general': TEST_QUERIES['general'][:2],
            'business_simple': TEST_QUERIES['business_simple'][:2],
        },
        'providers': ['gapgpt'],
        'models_per_provider': 2,  # فقط 2 مدل اول
    },
    
    'standard': {
        'name': 'تست استاندارد',
        'description': 'تست کامل با سوالات متنوع',
        'queries': {
            'classification': TEST_QUERIES['classification'],
            'general': TEST_QUERIES['general'],
            'business_simple': TEST_QUERIES['business_simple'],
            'business_complex': TEST_QUERIES['business_complex'][:2],
        },
        'providers': ['gapgpt', 'openai'],
        'models_per_provider': None,  # همه مدل‌ها
    },
    
    'comprehensive': {
        'name': 'تست جامع',
        'description': 'تست کامل تمام ترکیبات',
        'queries': TEST_QUERIES,  # همه سوالات
        'providers': ['gapgpt', 'openai'],
        'models_per_provider': None,  # همه مدل‌ها
    },
    
    'quality': {
        'name': 'تست کیفیت',
        'description': 'تست کیفیت پاسخ‌ها برای مقایسه مدل‌ها',
        'queries': {
            'business_simple': TEST_QUERIES['business_simple'],
            'business_complex': TEST_QUERIES['business_complex'],
        },
        'providers': ['gapgpt'],
        'models_per_provider': None,
    },
    
    'timing': {
        'name': 'تست زمان‌سنجی',
        'description': 'تست سرعت و زمان پاسخ‌دهی',
        'queries': {
            'business_timing': TEST_QUERIES['business_timing'],
        },
        'providers': ['gapgpt', 'openai'],
        'models_per_provider': None,
    }
}

# =============================================================================
# Benchmark History (نتایج تست‌های قبلی)
# =============================================================================

BENCHMARK_HISTORY = {
    '2026-02-16': {
        'description': 'تست جامع فوریه 2026 - مقایسه GapGPT و OpenAI',
        'results': {
            'gapgpt': {
                'gpt-4o-mini': {
                    'avg_time_ms': 6987,
                    'avg_tokens': 2100,
                    'success_rate': 1.0,
                    'quality_score': 7.9
                },
                'gpt-5-mini': {
                    'avg_time_ms': 7055,
                    'avg_tokens': 2150,
                    'success_rate': 1.0,
                    'quality_score': 8.7
                },
                'gpt-5.1': {
                    'avg_time_ms': 7447,
                    'avg_tokens': 2200,
                    'success_rate': 1.0,
                    'quality_score': 8.5
                },
                'gpt-5.2-chat-latest': {
                    'avg_time_ms': 7008,
                    'avg_tokens': 2180,
                    'success_rate': 1.0,
                    'quality_score': 9.5
                }
            },
            'openai': {
                'gpt-4o-mini': {
                    'avg_time_ms': 11838,
                    'avg_tokens': 2300,
                    'success_rate': 1.0,
                    'quality_score': 8.0
                },
                'gpt-4o': {
                    'avg_time_ms': 10577,
                    'avg_tokens': 2279,
                    'success_rate': 1.0,
                    'quality_score': 9.0,
                    'note': 'نوسان زمان زیاد (6.8s - 17.6s)'
                }
            }
        },
        'recommendations': {
            'classification': 'gapgpt/gpt-4o-mini',
            'llm1': 'gapgpt/gpt-4o-mini',
            'llm2': 'gapgpt/gpt-5-mini',
            'fallback': 'openai/gpt-4o-mini'
        }
    }
}

# =============================================================================
# Helper Functions
# =============================================================================

def get_provider_config(provider_key: str) -> dict:
    """دریافت تنظیمات یک provider"""
    return PROVIDERS.get(provider_key, {})

def get_llm_type_config(llm_type: str) -> dict:
    """دریافت تنظیمات یک نوع LLM"""
    return LLM_TYPES.get(llm_type, {})

def get_test_config(config_name: str) -> dict:
    """دریافت تنظیمات یک نوع تست"""
    return TEST_CONFIGS.get(config_name, TEST_CONFIGS['standard'])

def get_queries_for_test(test_type: str, category: str = None) -> list:
    """دریافت سوالات برای یک نوع تست"""
    if category:
        return TEST_QUERIES.get(category, [])
    return TEST_QUERIES.get(test_type, [])

def list_available_models(provider_key: str = None) -> dict:
    """لیست مدل‌های موجود"""
    if provider_key:
        provider = PROVIDERS.get(provider_key, {})
        return {provider_key: provider.get('models', [])}
    
    return {k: v.get('models', []) for k, v in PROVIDERS.items()}

def get_recommended_model(llm_type: str, provider_key: str) -> str:
    """دریافت مدل پیشنهادی برای یک نوع LLM و provider"""
    llm_config = LLM_TYPES.get(llm_type, {})
    recommended = llm_config.get('recommended_models', {})
    return recommended.get(provider_key, '')
