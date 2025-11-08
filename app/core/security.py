"""
Security Module
JWT authentication and authorization
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
import structlog

from app.config.settings import settings
from app.core.exceptions import (
    InvalidTokenException,
    InvalidAPIKeyException,
    to_http_exception
)

logger = structlog.get_logger()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token scheme
bearer_scheme = HTTPBearer()


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Token payload data
        expires_delta: Optional expiration time
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Token payload data
        expires_delta: Optional expiration time
        
    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.refresh_token_expire_days
        )
    
    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Decoded token payload
        
    Raises:
        InvalidTokenException: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
        
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        raise InvalidTokenException("Invalid or expired authentication token")


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> str:
    """
    Get current user ID from JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        User ID from token
        
    Raises:
        InvalidTokenException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    try:
        payload = verify_token(token)
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise InvalidTokenException("Invalid token payload: missing user ID")
        
        return user_id
        
    except InvalidTokenException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user from token: {e}")
        raise InvalidTokenException("Could not validate credentials")


def _hash_api_key(api_key: str) -> str:
    """
    Hash an API key using SHA-256.
    
    Args:
        api_key: API key to hash
        
    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def _constant_time_compare(val1: str, val2: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.
    
    Args:
        val1: First string
        val2: Second string
        
    Returns:
        True if strings match, False otherwise
    """
    return hmac.compare_digest(val1, val2)


async def verify_api_key(api_key: str) -> bool:
    """
    Verify an API key with timing attack protection.
    
    This function uses constant-time comparison to prevent timing attacks
    that could be used to guess valid API keys.
    
    Args:
        api_key: API key to verify
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        InvalidAPIKeyException: If API key is invalid
    """
    if not api_key:
        return False
    
    # Hash the provided key
    provided_hash = _hash_api_key(api_key)
    
    # For inter-service communication - compare hashes
    # In production, store hashed keys in database or secure vault
    valid_keys = [
        _hash_api_key(settings.ingest_api_key),
        _hash_api_key(settings.users_api_key),
    ]
    
    # Use constant-time comparison for each valid key
    for valid_key_hash in valid_keys:
        if _constant_time_compare(provided_hash, valid_key_hash):
            return True
    
    return False


async def verify_api_key_or_raise(api_key: str) -> str:
    """
    Verify API key and raise exception if invalid.
    
    Args:
        api_key: API key to verify
        
    Returns:
        The API key if valid
        
    Raises:
        InvalidAPIKeyException: If API key is invalid
    """
    if not await verify_api_key(api_key):
        raise InvalidAPIKeyException("Invalid or missing API key")
    return api_key


def hash_password(password: str) -> str:
    """
    Hash a password.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)
