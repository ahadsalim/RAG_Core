#!/bin/bash

# Test Core API endpoints inside container

BASE_URL="http://localhost:7001"
JWT_SECRET="VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo"

echo "=========================================="
echo "Testing Core API Endpoints"
echo "=========================================="

# Create JWT token using Python
TOKEN=$(python3 -c "
from jose import jwt
from datetime import datetime, timedelta

payload = {
    'sub': 'test-user-123',
    'exp': datetime.utcnow() + timedelta(minutes=30),
    'iat': datetime.utcnow()
}
print(jwt.encode(payload, '$JWT_SECRET', algorithm='HS256'))
")

echo "JWT Token created: ${TOKEN:0:50}..."
echo ""

# Test 1: Health Check
echo "1. Testing Health Check..."
curl -s -X GET "$BASE_URL/api/v1/health" | jq '.' || echo "Failed"
echo ""

# Test 2: User Profile
echo "2. Testing User Profile..."
curl -s -X GET "$BASE_URL/api/v1/users/profile" \
  -H "Authorization: Bearer $TOKEN" | jq '.' || echo "Failed"
echo ""

# Test 3: User Statistics
echo "3. Testing User Statistics..."
curl -s -X GET "$BASE_URL/api/v1/users/statistics" \
  -H "Authorization: Bearer $TOKEN" | jq '.' || echo "Failed"
echo ""

# Test 4: User Conversations
echo "4. Testing User Conversations..."
curl -s -X GET "$BASE_URL/api/v1/users/conversations" \
  -H "Authorization: Bearer $TOKEN" | jq '.' || echo "Failed"
echo ""

# Test 5: Simple Query
echo "5. Testing Simple Query..."
curl -s -X POST "$BASE_URL/api/v1/query/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "تست سیستم",
    "language": "fa",
    "max_results": 3,
    "use_cache": false,
    "use_reranking": false
  }' | jq '.' || echo "Failed"
echo ""

echo "=========================================="
echo "Tests completed!"
echo "=========================================="
