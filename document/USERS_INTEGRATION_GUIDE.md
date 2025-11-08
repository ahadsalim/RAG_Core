# 👥 راهنمای کامل یکپارچه‌سازی با سیستم کاربران

این راهنما به شما کمک می‌کند سیستم مدیریت کاربران خود را به Core System متصل کنید.

## 📋 فهرست

- [معماری کلی](#معماری-کلی)
- [پیش‌نیازها](#پیشنیازها)
- [تنظیمات اولیه](#تنظیمات-اولیه)
- [پیاده‌سازی در Users System](#پیادهسازی-در-users-system)
- [مدیریت User Tiers](#مدیریت-user-tiers)
- [مثال‌های کامل](#مثالهای-کامل)
- [عیب‌یابی](#عیبیابی)

---

## معماری کلی

```
┌─────────────────────────────────────────────────────────────┐
│                    سیستم کاربران (Users System)              │
│  - ثبت‌نام و ورود کاربران                                   │
│  - مدیریت پروفایل و tier                                     │
│  - تولید JWT Token                                          │
│  - رابط کاربری (UI)                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTP Request + JWT Token
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  سیستم مرکزی (Core System)                   │
│  - احراز هویت JWT                                           │
│  - Rate Limiting                                            │
│  - پردازش Query با RAG                                      │
│  - مدیریت Conversation                                      │
│  - ذخیره تاریخچه                                            │
└─────────────────────────────────────────────────────────────┘
```

### تقسیم مسئولیت‌ها:

| مسئولیت | Users System | Core System |
|---------|--------------|-------------|
| ثبت‌نام کاربر | ✅ | ❌ |
| Login/Logout | ✅ | ❌ |
| تولید JWT Token | ✅ | ❌ |
| Verify JWT Token | ❌ | ✅ |
| مدیریت Tier | ✅ | ✅ (خواندن) |
| Rate Limiting | ❌ | ✅ |
| پردازش Query | ❌ | ✅ |
| ذخیره مکالمات | ❌ | ✅ |

---

## پیش‌نیازها

### 1. کتابخانه‌های Python

```bash
# در سیستم Users خود
pip install python-jose[cryptography]
pip install passlib[bcrypt]
pip install httpx
pip install pydantic-settings
```

### 2. دریافت JWT Secret Key از Core

```bash
# در سرور Core
cd /srv
cat .env | grep JWT_SECRET_KEY

# خروجی:
# JWT_SECRET_KEY="X4eHq1k/FUpfdAuxlCcwLZsoVvzk3YQLY5uFHeKlmNEKttv6KCha172oibsalOGq"
```

---

## تنظیمات اولیه

### 1. ایجاد فایل `.env` در Users System

```bash
# در پروژه Users System
touch .env
```

محتوای `.env`:

```bash
# JWT Settings (باید با Core یکسان باشد!)
JWT_SECRET_KEY="X4eHq1k/FUpfdAuxlCcwLZsoVvzk3YQLY5uFHeKlmNEKttv6KCha172oibsalOGq"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Core System
CORE_API_URL="http://localhost:7001"
CORE_API_TIMEOUT=30

# Database (مثال)
DATABASE_URL="postgresql://user:pass@localhost:5432/users_db"
REDIS_URL="redis://localhost:6379/1"

# Application
APP_NAME="Users Management System"
DEBUG=true
```

### 2. اضافه کردن `.env` به `.gitignore`

```bash
# .gitignore
.env
.env.local
.env.production
*.env
__pycache__/
*.pyc
```

---

## پیاده‌سازی در Users System

### ساختار پیشنهادی:

```
users-system/
├── app/
│   ├── config/
│   │   └── settings.py          # تنظیمات
│   ├── auth/
│   │   ├── jwt.py               # JWT utilities
│   │   └── dependencies.py      # FastAPI dependencies
│   ├── services/
│   │   └── core_client.py       # Client برای Core
│   ├── api/
│   │   ├── auth.py              # Login/Register endpoints
│   │   └── chat.py              # Chat endpoints
│   └── models/
│       └── user.py              # User model
├── .env
└── main.py
```

### 1. تنظیمات (config/settings.py)

```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    """تنظیمات سیستم Users"""
    
    # Application
    app_name: str = "Users Management System"
    debug: bool = False
    
    # JWT Settings (باید با Core یکسان باشد!)
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Core System
    core_api_url: str = "http://localhost:7001"
    core_api_timeout: int = 30
    
    # Database
    database_url: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# بررسی امنیت
settings = Settings()

if len(settings.jwt_secret_key) < 32:
    raise ValueError("JWT_SECRET_KEY must be at least 32 characters!")
```

### 2. JWT Utilities (auth/jwt.py)

```python
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from app.config.settings import settings

def create_access_token(
    user_id: str,
    tier: str = "FREE",
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    تولید JWT token برای کاربر.
    
    Args:
        user_id: شناسه کاربر (UUID)
        tier: سطح کاربر (FREE, BASIC, PREMIUM, ENTERPRISE)
        additional_claims: داده‌های اضافی
        
    Returns:
        JWT token string
    """
    # محاسبه زمان انقضا
    expire = datetime.utcnow() + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    
    # ساخت payload
    payload = {
        "sub": user_id,  # subject = user_id (الزامی)
        "tier": tier,
        "iat": datetime.utcnow(),  # issued at
        "exp": expire,  # expiration
    }
    
    # اضافه کردن claims اضافی
    if additional_claims:
        payload.update(additional_claims)
    
    # رمزنگاری با SECRET_KEY
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    return token


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Verify کردن JWT token.
    
    Args:
        token: JWT token
        
    Returns:
        Decoded payload
        
    Raises:
        ValueError: اگر token نامعتبر باشد
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {str(e)}")


def decode_token_without_verification(token: str) -> Dict[str, Any]:
    """
    Decode کردن token بدون verify (برای دیباگ).
    
    ⚠️ فقط برای development!
    """
    return jwt.decode(
        token,
        options={"verify_signature": False}
    )
```

### 3. Core Client (services/core_client.py)

```python
import httpx
from typing import Optional, Dict, Any
from fastapi import HTTPException
import structlog
from app.config.settings import settings

logger = structlog.get_logger()


class CoreClient:
    """
    کلاینت برای ارتباط با Core System.
    """
    
    def __init__(self):
        self.base_url = settings.core_api_url
        self.timeout = httpx.Timeout(settings.core_api_timeout)
    
    async def send_query(
        self,
        jwt_token: str,
        query: str,
        conversation_id: Optional[str] = None,
        language: str = "fa",
        max_results: int = 5,
        use_cache: bool = True,
        use_reranking: bool = True
    ) -> Dict[str, Any]:
        """
        ارسال query به Core System.
        
        Args:
            jwt_token: JWT token کاربر
            query: متن سوال
            conversation_id: شناسه مکالمه (برای ادامه چت)
            language: زبان پاسخ (fa, en, ar)
            max_results: تعداد نتایج
            use_cache: استفاده از cache
            use_reranking: استفاده از reranking
            
        Returns:
            پاسخ از Core system
            
        Raises:
            HTTPException: در صورت خطا
        """
        url = f"{self.base_url}/api/v1/query"
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "language": language,
            "max_results": max_results,
            "use_cache": use_cache,
            "use_reranking": use_reranking
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    return response.json()
                
                elif response.status_code == 401:
                    logger.error("Unauthorized: Invalid JWT token")
                    raise HTTPException(
                        status_code=401,
                        detail="توکن نامعتبر است. لطفاً دوباره وارد شوید."
                    )
                
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning(f"Rate limit exceeded. Retry after {retry_after}s")
                    raise HTTPException(
                        status_code=429,
                        detail=f"محدودیت تعداد درخواست. لطفاً {retry_after} ثانیه صبر کنید."
                    )
                
                elif response.status_code == 503:
                    logger.error("Core system unavailable")
                    raise HTTPException(
                        status_code=503,
                        detail="سیستم موقتاً در دسترس نیست. لطفاً بعداً تلاش کنید."
                    )
                
                else:
                    logger.error(f"Core system error: {response.status_code}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail="خطا در پردازش درخواست"
                    )
        
        except httpx.TimeoutException:
            logger.error("Request to Core system timed out")
            raise HTTPException(
                status_code=504,
                detail="زمان پاسخ‌دهی تمام شد. لطفاً دوباره تلاش کنید."
            )
        
        except httpx.ConnectError:
            logger.error("Cannot connect to Core system")
            raise HTTPException(
                status_code=503,
                detail="امکان اتصال به سیستم وجود ندارد."
            )
    
    async def send_query_stream(
        self,
        jwt_token: str,
        query: str,
        conversation_id: Optional[str] = None,
        language: str = "fa"
    ):
        """
        ارسال query با streaming response.
        
        Yields:
            Chunks of response
        """
        url = f"{self.base_url}/api/v1/query/stream"
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "language": language
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    raise HTTPException(response.status_code, "Streaming failed")
                
                async for line in response.aiter_lines():
                    if line:
                        yield line
    
    async def get_conversation_history(
        self,
        jwt_token: str,
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        دریافت تاریخچه مکالمه.
        """
        url = f"{self.base_url}/api/v1/conversations/{conversation_id}"
        headers = {"Authorization": f"Bearer {jwt_token}"}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    
    async def submit_feedback(
        self,
        jwt_token: str,
        message_id: str,
        rating: int,
        feedback_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ارسال بازخورد کاربر.
        """
        url = f"{self.base_url}/api/v1/query/feedback"
        headers = {"Authorization": f"Bearer {jwt_token}"}
        
        payload = {
            "message_id": message_id,
            "rating": rating,
            "feedback_type": "general"
        }
        
        if feedback_text:
            payload["feedback_text"] = feedback_text
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    
    async def health_check(self) -> bool:
        """
        بررسی سلامت Core System.
        """
        try:
            url = f"{self.base_url}/health"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except:
            return False


# Singleton instance
core_client = CoreClient()
```

### 4. Authentication API (api/auth.py)

```python
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from app.auth.jwt import create_access_token
from app.db.session import get_db
from app.models.user import User

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: dict


@router.post("/register")
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    ثبت‌نام کاربر جدید.
    """
    # بررسی وجود کاربر
    existing_user = await db.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(400, "این ایمیل قبلاً ثبت شده است")
    
    # ساخت کاربر جدید
    hashed_password = pwd_context.hash(request.password)
    
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hashed_password,
        tier="FREE"  # tier پیش‌فرض
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return {
        "message": "ثبت‌نام با موفقیت انجام شد",
        "user_id": str(user.id)
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    ورود کاربر و تولید JWT token.
    """
    # پیدا کردن کاربر
    user = await db.get_user_by_username(form_data.username)
    if not user:
        raise HTTPException(401, "نام کاربری یا رمز عبور اشتباه است")
    
    # بررسی password
    if not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(401, "نام کاربری یا رمز عبور اشتباه است")
    
    # تولید JWT token
    access_token = create_access_token(
        user_id=str(user.id),
        tier=user.tier,
        additional_claims={
            "username": user.username,
            "email": user.email
        }
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=1800,  # 30 minutes
        user={
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "tier": user.tier
        }
    )
```

### 5. Chat API (api/chat.py)

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
from app.auth.dependencies import get_current_user, get_jwt_token
from app.services.core_client import core_client
from app.models.user import User

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    conversation_id: str
    message_id: str
    answer: str
    sources: list
    tokens_used: int


@router.post("/send-message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    jwt_token: str = Depends(get_jwt_token)
):
    """
    ارسال پیام به Core System.
    """
    try:
        # ارسال به Core
        result = await core_client.send_query(
            jwt_token=jwt_token,
            query=request.message,
            conversation_id=request.conversation_id
        )
        
        return ChatResponse(
            success=True,
            conversation_id=result["conversation_id"],
            message_id=result["message_id"],
            answer=result["answer"],
            sources=result["sources"],
            tokens_used=result["tokens_used"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"خطا در ارسال پیام: {str(e)}")


@router.get("/history/{conversation_id}")
async def get_history(
    conversation_id: str,
    jwt_token: str = Depends(get_jwt_token)
):
    """
    دریافت تاریخچه مکالمه.
    """
    result = await core_client.get_conversation_history(
        jwt_token=jwt_token,
        conversation_id=conversation_id
    )
    return result
```

---

## مدیریت User Tiers

### Tier Levels و محدودیت‌ها:

| Tier | Per Minute | Per Hour | Per Day | قیمت (مثال) |
|------|------------|----------|---------|-------------|
| FREE | 5 | 50 | 100 | رایگان |
| BASIC | 10 | 200 | 1000 | $10/ماه |
| PREMIUM | 30 | 1000 | 10000 | $50/ماه |
| ENTERPRISE | 100 | 5000 | 50000 | تماس با فروش |

### Upgrade کردن کاربر:

```python
# api/subscription.py
from fastapi import APIRouter, Depends
from app.models.user import User
from app.auth.dependencies import get_current_user

router = APIRouter()

@router.post("/upgrade")
async def upgrade_tier(
    new_tier: str,  # BASIC, PREMIUM, ENTERPRISE
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upgrade tier کاربر.
    
    در production:
    1. بررسی پرداخت
    2. تأیید transaction
    3. تغییر tier
    """
    # بررسی tier معتبر
    valid_tiers = ["FREE", "BASIC", "PREMIUM", "ENTERPRISE"]
    if new_tier not in valid_tiers:
        raise HTTPException(400, "Tier نامعتبر است")
    
    # TODO: بررسی پرداخت
    # payment_verified = await verify_payment(...)
    
    # تغییر tier
    current_user.tier = new_tier
    await db.commit()
    
    # Core خودکار محدودیت‌های جدید را اعمال می‌کند
    
    return {
        "message": f"Tier شما به {new_tier} ارتقا یافت",
        "new_limits": {
            "per_minute": get_tier_limits(new_tier)["per_minute"],
            "per_hour": get_tier_limits(new_tier)["per_hour"],
            "per_day": get_tier_limits(new_tier)["per_day"]
        }
    }
```

---

## مثال‌های کامل

### مثال 1: فلوی کامل Login و Query

```python
# 1. کاربر login می‌کند
login_response = await client.post("/auth/login", data={
    "username": "ali@example.com",
    "password": "password123"
})

token = login_response.json()["access_token"]
# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 2. ارسال query به Core
chat_response = await client.post(
    "/chat/send-message",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "message": "ماده 10 قانون مدنی چیست؟"
    }
)

result = chat_response.json()
print(result["answer"])
# "ماده 10 قانون مدنی..."

# 3. ادامه مکالمه
chat_response2 = await client.post(
    "/chat/send-message",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "message": "توضیح بیشتر بده",
        "conversation_id": result["conversation_id"]
    }
)
```

### مثال 2: Streaming Response

```python
from fastapi.responses import StreamingResponse

@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    jwt_token: str = Depends(get_jwt_token)
):
    """
    Chat با streaming response.
    """
    async def generate():
        async for chunk in core_client.send_query_stream(
            jwt_token=jwt_token,
            query=request.message,
            conversation_id=request.conversation_id
        ):
            yield chunk + "\n"
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson"
    )
```

---

## عیب‌یابی

### مشکل 1: Token نامعتبر است (401)

```python
# بررسی:
from app.auth.jwt import decode_token_without_verification

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
payload = decode_token_without_verification(token)
print(payload)

# بررسی کنید:
# 1. exp (expiration) منقضی نشده باشد
# 2. sub (user_id) موجود باشد
# 3. JWT_SECRET_KEY در Users و Core یکسان باشد
```

### مشکل 2: Rate Limit (429)

```python
# راه‌حل:
# 1. Tier کاربر را بررسی کنید
# 2. منتظر بمانید (Retry-After header)
# 3. به کاربر پیشنهاد upgrade دهید

if response.status_code == 429:
    retry_after = response.headers.get("Retry-After")
    print(f"لطفاً {retry_after} ثانیه صبر کنید")
```

### مشکل 3: Core در دسترس نیست (503)

```python
# بررسی:
health = await core_client.health_check()
if not health:
    print("Core System آفلاین است")
    # نمایش پیام به کاربر
```

### تست کامل:

```python
# test_integration.py
import asyncio
from app.services.core_client import core_client
from app.auth.jwt import create_access_token

async def test_full_flow():
    # 1. تولید token
    token = create_access_token(
        user_id="test-user-123",
        tier="PREMIUM"
    )
    print(f"Token: {token[:50]}...")
    
    # 2. بررسی سلامت Core
    health = await core_client.health_check()
    print(f"Core Health: {health}")
    
    # 3. ارسال query
    try:
        result = await core_client.send_query(
            jwt_token=token,
            query="ماده 10 قانون مدنی چیست؟"
        )
        print(f"Answer: {result['answer'][:100]}...")
        print(f"Conversation ID: {result['conversation_id']}")
    except Exception as e:
        print(f"Error: {e}")

# اجرا
asyncio.run(test_full_flow())
```

---

## نکات امنیتی

### ✅ Do's:
- JWT_SECRET_KEY را در `.env` نگهداری کنید
- HTTPS در production استفاده کنید
- Token expiration را رعایت کنید
- Rate limiting را در UI نمایش دهید
- Error handling مناسب پیاده کنید

### ❌ Don'ts:
- JWT_SECRET_KEY را در کد commit نکنید
- Token را در localStorage ذخیره نکنید (XSS risk)
- SECRET_KEY را با کسی share نکنید
- Token را در URL query parameter نفرستید

---

## منابع بیشتر

- [Core API Documentation](http://localhost:7001/docs)
- [JWT.io](https://jwt.io) - برای debug کردن tokens
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

---

**آخرین بروزرسانی**: 8 نوامبر 2024
