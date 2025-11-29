#!/usr/bin/env python3
"""
تست ساده API - بررسی دریافت پاسخ
"""

import requests
import json

# تنظیمات
RAG_CORE_URL = "http://localhost:7001"
JWT_TOKEN = "your_test_token_here"  # باید یک token معتبر باشد

def test_simple_query():
    """تست query ساده بدون فایل"""
    
    url = f"{RAG_CORE_URL}/api/v1/query/"
    
    payload = {
        "query": "قانون مدنی چیست؟",
        "language": "fa",
        "max_results": 5
    }
    
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print("📤 ارسال درخواست...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"\n📥 پاسخ دریافت شد:")
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ موفق!")
            print(f"Answer: {result.get('answer', 'N/A')[:200]}...")
            print(f"Sources: {result.get('sources', [])}")
            print(f"Tokens: {result.get('tokens_used', 0)}")
            print(f"Time: {result.get('processing_time_ms', 0)}ms")
            return True
        else:
            print(f"\n❌ خطا!")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("\n⏱️ Timeout! سرور پاسخ نداد.")
        return False
    except requests.exceptions.ConnectionError:
        print("\n🔌 Connection Error! سرور در دسترس نیست.")
        return False
    except Exception as e:
        print(f"\n💥 خطای غیرمنتظره: {e}")
        return False


def test_query_with_file():
    """تست query با فایل (لینک MinIO)"""
    
    url = f"{RAG_CORE_URL}/api/v1/query/"
    
    payload = {
        "query": "این سند چه می‌گوید؟",
        "language": "fa",
        "max_results": 5,
        "file_attachments": [
            {
                "filename": "test_document.pdf",
                "minio_url": "temp_uploads/test_user/20241129_120000_test_doc.pdf",
                "file_type": "application/pdf",
                "size_bytes": 1024000
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print("\n" + "="*60)
    print("📤 تست با فایل...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"\n📥 پاسخ دریافت شد:")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ موفق!")
            print(f"Answer: {result.get('answer', 'N/A')[:200]}...")
            print(f"Files Processed: {result.get('files_processed', 0)}")
            return True
        else:
            print(f"\n❌ خطا!")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n💥 خطا: {e}")
        return False


def check_api_health():
    """بررسی سلامت API"""
    
    url = f"{RAG_CORE_URL}/api/v1/health/"
    
    print("🏥 بررسی سلامت API...")
    
    try:
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            print("✅ API سالم است")
            return True
        else:
            print(f"⚠️ API مشکل دارد: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ API در دسترس نیست: {e}")
        return False


if __name__ == "__main__":
    print("🧪 شروع تست API")
    print("="*60)
    
    # 1. بررسی سلامت
    if not check_api_health():
        print("\n⚠️ API در دسترس نیست. لطفا سرور را راه‌اندازی کنید.")
        exit(1)
    
    # 2. تست query ساده
    print("\n" + "="*60)
    result1 = test_simple_query()
    
    # 3. تست query با فایل
    result2 = test_query_with_file()
    
    # خلاصه
    print("\n" + "="*60)
    print("📊 خلاصه نتایج:")
    print(f"  - Query ساده: {'✅ موفق' if result1 else '❌ ناموفق'}")
    print(f"  - Query با فایل: {'✅ موفق' if result2 else '❌ ناموفق'}")
    print("="*60)
