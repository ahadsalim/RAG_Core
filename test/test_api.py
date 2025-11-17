#!/usr/bin/env python3
"""Test Core API endpoints"""

import requests
import json
from jose import jwt
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:7001"
JWT_SECRET = "VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo"

def create_test_token(user_id="test-user-123"):
    """Create a test JWT token"""
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def test_endpoint(name, method, url, headers=None, json_data=None):
    """Test an endpoint and print results"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"Method: {method}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=json_data, timeout=30)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS")
            try:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
            except:
                print(f"Response: {response.text[:200]}")
        else:
            print("❌ FAILED")
            print(f"Error: {response.text[:500]}")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

# Create JWT token
token = create_test_token()
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

print("JWT Token created successfully")
print(f"Token: {token[:50]}...")

# Test endpoints
test_endpoint(
    "Health Check",
    "GET",
    f"{BASE_URL}/api/v1/health"
)

test_endpoint(
    "User Profile",
    "GET",
    f"{BASE_URL}/api/v1/users/profile",
    headers=headers
)

test_endpoint(
    "User Statistics",
    "GET",
    f"{BASE_URL}/api/v1/users/statistics",
    headers=headers
)

test_endpoint(
    "User Conversations",
    "GET",
    f"{BASE_URL}/api/v1/users/conversations",
    headers=headers
)

test_endpoint(
    "Simple Query",
    "POST",
    f"{BASE_URL}/api/v1/query/",
    headers=headers,
    json_data={
        "query": "تست سیستم",
        "language": "fa",
        "max_results": 3,
        "use_cache": False,
        "use_reranking": False
    }
)

print(f"\n{'='*60}")
print("Tests completed!")
