#!/usr/bin/env python3
"""Test Core API endpoints inside container"""

from jose import jwt
from datetime import datetime, timedelta
import requests
import json

JWT_SECRET = 'VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo'
BASE_URL = 'http://localhost:7001'

# Create token
payload = {
    'sub': 'test-user-123',
    'exp': datetime.utcnow() + timedelta(minutes=30)
}
token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

print('='*60)
print('Testing Core API Endpoints')
print('='*60)

# Test 1: Health Check
print('\n1. Health Check')
try:
    r = requests.get(f'{BASE_URL}/api/v1/health', timeout=5)
    status_icon = '✅' if r.status_code == 200 else '❌'
    print(f'   Status: {r.status_code} {status_icon}')
except Exception as e:
    print(f'   Error: {e} ❌')

# Test 2: User Profile
print('\n2. User Profile')
try:
    r = requests.get(f'{BASE_URL}/api/v1/users/profile', headers=headers, timeout=5)
    status_icon = '✅' if r.status_code == 200 else '❌'
    print(f'   Status: {r.status_code} {status_icon}')
    if r.status_code != 200:
        print(f'   Error: {r.text[:200]}')
except Exception as e:
    print(f'   Error: {e} ❌')

# Test 3: User Statistics
print('\n3. User Statistics')
try:
    r = requests.get(f'{BASE_URL}/api/v1/users/statistics', headers=headers, timeout=5)
    status_icon = '✅' if r.status_code == 200 else '❌'
    print(f'   Status: {r.status_code} {status_icon}')
    if r.status_code != 200:
        print(f'   Error: {r.text[:200]}')
except Exception as e:
    print(f'   Error: {e} ❌')

# Test 4: User Conversations
print('\n4. User Conversations')
try:
    r = requests.get(f'{BASE_URL}/api/v1/users/conversations', headers=headers, timeout=5)
    status_icon = '✅' if r.status_code == 200 else '❌'
    print(f'   Status: {r.status_code} {status_icon}')
    if r.status_code != 200:
        print(f'   Error: {r.text[:200]}')
except Exception as e:
    print(f'   Error: {e} ❌')

# Test 5: Simple Query
print('\n5. Simple Query')
try:
    r = requests.post(f'{BASE_URL}/api/v1/query/', headers=headers, json={
        'query': 'تست سیستم',
        'language': 'fa',
        'max_results': 3,
        'use_cache': False,
        'use_reranking': False
    }, timeout=30)
    status_icon = '✅' if r.status_code == 200 else '❌'
    print(f'   Status: {r.status_code} {status_icon}')
    if r.status_code == 200:
        data = r.json()
        print(f'   Answer: {data.get("answer", "")[:100]}...')
        print(f'   Tokens: {data.get("tokens_used", 0)}')
    else:
        print(f'   Error: {r.text[:300]}')
except Exception as e:
    print(f'   Error: {e} ❌')

print('\n' + '='*60)
print('Tests Completed!')
print('='*60)
