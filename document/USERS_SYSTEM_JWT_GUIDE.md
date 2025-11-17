# JWT Configuration Guide for Users System

## Problem
Users system is getting "Invalid JWT" error when sending user information to Core system.

## Root Cause
The JWT tokens must be signed with the **same secret key** that Core uses for verification.

---

## Solution: JWT Configuration

### 1. JWT Secret Key

**Users system MUST use this exact value:**

```env
JWT_SECRET_KEY="VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo"
JWT_ALGORITHM="HS256"
```

⚠️ **CRITICAL:** This value must be **exactly the same** in both systems:
- Core system: `/srv/.env`
- Users system: `<users_system>/.env`

---

## How JWT Works Between Systems

### Architecture

```
User → Users System → Creates JWT → Sends to Core → Core Verifies JWT
```

### Flow

1. **User logs in to Users System**
2. **Users System creates JWT:**
   ```python
   payload = {
       "sub": user_id,  # User ID
       "exp": expiration_time
   }
   token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")
   ```

3. **Users System sends request to Core:**
   ```http
   POST https://core.domain.com/api/v1/query/
   Authorization: Bearer {token}
   
   {
     "query": "سوال کاربر"
   }
   ```

4. **Core verifies JWT:**
   ```python
   # Core extracts user_id from token
   payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
   user_id = payload.get("sub")
   ```

---

## Implementation in Users System

### Python Example (Django/FastAPI)

```python
from jose import jwt
from datetime import datetime, timedelta

# Configuration (from .env)
JWT_SECRET_KEY = "VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token_for_core(user_id: str) -> str:
    """
    Create JWT token for Core system authentication.
    
    Args:
        user_id: Unique user identifier
        
    Returns:
        JWT token string
    """
    payload = {
        "sub": user_id,  # REQUIRED: Core expects user_id in 'sub' field
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow(),  # Optional: issued at
    }
    
    token = jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )
    
    return token

# Usage
user_id = "user-123"
token = create_access_token_for_core(user_id)

# Send to Core
import requests
response = requests.post(
    "https://core.domain.com/api/v1/query/",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    json={
        "query": "سوال کاربر"
    }
)
```

### Node.js Example

```javascript
const jwt = require('jsonwebtoken');

// Configuration (from .env)
const JWT_SECRET_KEY = "VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo";
const JWT_ALGORITHM = "HS256";
const ACCESS_TOKEN_EXPIRE_MINUTES = 30;

function createAccessTokenForCore(userId) {
    const payload = {
        sub: userId,  // REQUIRED: Core expects user_id in 'sub' field
        exp: Math.floor(Date.now() / 1000) + (ACCESS_TOKEN_EXPIRE_MINUTES * 60),
        iat: Math.floor(Date.now() / 1000)
    };
    
    const token = jwt.sign(payload, JWT_SECRET_KEY, {
        algorithm: JWT_ALGORITHM
    });
    
    return token;
}

// Usage
const userId = "user-123";
const token = createAccessTokenForCore(userId);

// Send to Core
const axios = require('axios');
axios.post('https://core.domain.com/api/v1/query/', {
    query: "سوال کاربر"
}, {
    headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    }
});
```

---

## Token Payload Structure

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `sub` | string | User ID (subject) | `"user-123"` |
| `exp` | integer | Expiration timestamp (Unix) | `1763362313` |

### Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `iat` | integer | Issued at timestamp | `1763360513` |
| `type` | string | Token type | `"access"` |

### Example Payload

```json
{
  "sub": "user-123",
  "exp": 1763362313,
  "iat": 1763360513
}
```

---

## Testing

### 1. Test Token Creation

```python
from jose import jwt
from datetime import datetime, timedelta

JWT_SECRET_KEY = "VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo"
JWT_ALGORITHM = "HS256"

# Create token
user_id = "test-user-123"
payload = {
    "sub": user_id,
    "exp": datetime.utcnow() + timedelta(minutes=30)
}

token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
print(f"Token: {token}")

# Verify token
decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
print(f"User ID: {decoded.get('sub')}")
```

### 2. Test API Call to Core

```bash
# Create a test token (use Python script above)
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Test query endpoint
curl -X POST https://core.domain.com/api/v1/query/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "قانون مدنی چیست؟"
  }'
```

### Expected Response

```json
{
  "answer": "...",
  "sources": [...],
  "conversation_id": "uuid",
  "message_id": "uuid",
  "tokens_used": 150,
  "processing_time_ms": 1200
}
```

---

## Common Errors

### Error 1: "Invalid authentication token"

**Cause:** JWT_SECRET_KEY is different between Users and Core

**Solution:**
```env
# Users system .env - MUST match Core
JWT_SECRET_KEY="VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYarTaHf8i+mVo"
```

### Error 2: "Invalid token payload"

**Cause:** Missing `sub` field in JWT payload

**Solution:**
```python
# WRONG
payload = {"user_id": "123"}

# CORRECT
payload = {"sub": "123"}
```

### Error 3: Token expired

**Cause:** Token expiration time has passed

**Solution:**
```python
# Set appropriate expiration
payload = {
    "sub": user_id,
    "exp": datetime.utcnow() + timedelta(minutes=30)  # 30 minutes
}
```

---

## Security Best Practices

### 1. Keep Secret Key Secure

```bash
# ✅ GOOD: Use environment variables
JWT_SECRET_KEY="${JWT_SECRET_KEY}"

# ❌ BAD: Hardcode in source code
JWT_SECRET_KEY = "VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo"
```

### 2. Use HTTPS

```bash
# ✅ GOOD
https://core.domain.com/api/v1/query/

# ❌ BAD
http://core.domain.com/api/v1/query/
```

### 3. Set Appropriate Expiration

```python
# ✅ GOOD: Short expiration for access tokens
timedelta(minutes=30)

# ❌ BAD: Very long expiration
timedelta(days=365)
```

### 4. Validate Token on Every Request

```python
# Core automatically validates on every request
# Users system should also validate before forwarding
```

---

## Configuration Checklist

- [ ] Set `JWT_SECRET_KEY` in Users system `.env`
- [ ] Verify `JWT_SECRET_KEY` matches Core system
- [ ] Set `JWT_ALGORITHM="HS256"`
- [ ] Implement token creation function
- [ ] Include `sub` field with user_id in payload
- [ ] Set appropriate expiration time
- [ ] Test token creation and verification
- [ ] Test API call to Core with token
- [ ] Use HTTPS in production
- [ ] Keep secret key secure (environment variables)

---

## Support

If you still get "Invalid JWT" error after following this guide:

1. **Verify secret key matches:**
   ```bash
   # On Core server
   grep JWT_SECRET_KEY /srv/.env
   
   # On Users server
   grep JWT_SECRET_KEY <users_path>/.env
   ```

2. **Test token locally:**
   ```python
   # Use the Python test script above
   ```

3. **Check Core logs:**
   ```bash
   docker logs core-api --tail 50 | grep -i "token\|jwt\|auth"
   ```

4. **Contact Core team** with:
   - Sample token (without sensitive data)
   - Error message from Core
   - Users system configuration (without secret key)

---

## Summary

**The key point:** Users system MUST use the exact same `JWT_SECRET_KEY` as Core system:

```
JWT_SECRET_KEY="VbZrmDB32DKRIxZGQoAVmrDdkmTivR3Nu/JTEn8Uq+O6B4ZGtv0gYrTaHf8i+mVo"
```

This is the **only** way for Core to verify tokens created by Users system.
