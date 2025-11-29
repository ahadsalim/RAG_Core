"""
Test File Upload API
Test script for query endpoint with file attachments
"""

import requests
import os
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:7001/api/v1"
# Replace with your actual JWT token
JWT_TOKEN = "your_jwt_token_here"

HEADERS = {
    "Authorization": f"Bearer {JWT_TOKEN}"
}


def test_query_without_files():
    """Test basic query without files."""
    print("\n=== Test 1: Query without files ===")
    
    data = {
        "query": "قانون مدنی در مورد مالکیت چه می‌گوید؟",
        "language": "fa",
        "max_results": 5,
        "use_cache": True,
        "use_reranking": True
    }
    
    response = requests.post(
        f"{API_BASE_URL}/query/",
        data=data,
        headers=HEADERS
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Answer: {result['answer'][:200]}...")
        print(f"Sources: {result['sources']}")
        print(f"Tokens: {result['tokens_used']}")
    else:
        print(f"Error: {response.text}")


def test_query_with_text_file():
    """Test query with a text file."""
    print("\n=== Test 2: Query with text file ===")
    
    # Create a sample text file
    sample_text = """
    این یک متن نمونه است.
    قانون مدنی ایران در مورد مالکیت مقررات مختلفی دارد.
    ماده ۱۷۹: شکار کردن موجب تملک است.
    """
    
    temp_file = Path("/tmp/sample.txt")
    temp_file.write_text(sample_text, encoding='utf-8')
    
    data = {
        "query": "این سند چه می‌گوید؟",
        "language": "fa",
        "max_results": 5
    }
    
    files = {
        "files": ("sample.txt", open(temp_file, "rb"), "text/plain")
    }
    
    response = requests.post(
        f"{API_BASE_URL}/query/",
        data=data,
        files=files,
        headers=HEADERS
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Answer: {result['answer'][:200]}...")
        print(f"Conversation ID: {result['conversation_id']}")
    else:
        print(f"Error: {response.text}")
    
    # Cleanup
    temp_file.unlink()


def test_query_with_multiple_files():
    """Test query with multiple files."""
    print("\n=== Test 3: Query with multiple files ===")
    
    # Create sample files
    file1_content = "فایل اول: اطلاعات مربوط به قانون مدنی"
    file2_content = "فایل دوم: مقررات مالکیت"
    
    temp_file1 = Path("/tmp/file1.txt")
    temp_file2 = Path("/tmp/file2.txt")
    
    temp_file1.write_text(file1_content, encoding='utf-8')
    temp_file2.write_text(file2_content, encoding='utf-8')
    
    data = {
        "query": "خلاصه این اسناد را بگو",
        "language": "fa",
        "max_results": 5
    }
    
    files = [
        ("files", ("file1.txt", open(temp_file1, "rb"), "text/plain")),
        ("files", ("file2.txt", open(temp_file2, "rb"), "text/plain"))
    ]
    
    response = requests.post(
        f"{API_BASE_URL}/query/",
        data=data,
        files=files,
        headers=HEADERS
    )
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Answer: {result['answer'][:200]}...")
        print(f"Processing time: {result['processing_time_ms']}ms")
    else:
        print(f"Error: {response.text}")
    
    # Cleanup
    temp_file1.unlink()
    temp_file2.unlink()


def test_query_with_too_many_files():
    """Test query with more than 5 files (should fail)."""
    print("\n=== Test 4: Query with too many files (should fail) ===")
    
    # Create 6 sample files
    temp_files = []
    for i in range(6):
        temp_file = Path(f"/tmp/file{i}.txt")
        temp_file.write_text(f"File {i} content", encoding='utf-8')
        temp_files.append(temp_file)
    
    data = {
        "query": "تست",
        "language": "fa"
    }
    
    files = [
        ("files", (f"file{i}.txt", open(f, "rb"), "text/plain"))
        for i, f in enumerate(temp_files)
    ]
    
    response = requests.post(
        f"{API_BASE_URL}/query/",
        data=data,
        files=files,
        headers=HEADERS
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    # Cleanup
    for f in temp_files:
        f.unlink()


def test_health_check():
    """Test health check endpoint."""
    print("\n=== Test 0: Health Check ===")
    
    response = requests.get(f"{API_BASE_URL}/health/")
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {response.json()}")
    else:
        print(f"Error: {response.text}")


if __name__ == "__main__":
    print("=" * 60)
    print("File Upload API Test Suite")
    print("=" * 60)
    
    # Check if JWT token is set
    if JWT_TOKEN == "your_jwt_token_here":
        print("\n⚠️  WARNING: Please set your JWT_TOKEN in the script!")
        print("You can get a token by authenticating with the API.")
        print("\nSkipping tests that require authentication...")
        test_health_check()
    else:
        # Run all tests
        test_health_check()
        test_query_without_files()
        test_query_with_text_file()
        test_query_with_multiple_files()
        test_query_with_too_many_files()
    
    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)
