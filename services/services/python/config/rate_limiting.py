"""
Production-Ready Rate Limiting Middleware

This module provides rate limiting for all FastAPI services using Redis.
All configuration comes from environment variables.
"""

import os
import time
from typing import Callable, Optional
from functools import wraps

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

# Optional Redis import
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    redis = None


class RateLimiter:
    """Redis-based rate limiter for production use"""
    
    def __init__(self):
        self._redis_client = None
        self.default_limit = int(os.getenv("RATE_LIMIT_DEFAULT", "100"))
        self.default_window = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    
    def _get_redis(self):
        """Get Redis client - lazy initialization"""
        if self._redis_client is None:
            if not HAS_REDIS:
                return None
            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                return None
            try:
                self._redis_client = redis.from_url(redis_url, decode_responses=True)
            except Exception:
                return None
        return self._redis_client
    
    def is_rate_limited(
        self, 
        key: str, 
        limit: Optional[int] = None, 
        window: Optional[int] = None
    ) -> tuple[bool, int, int]:
        """
        Check if request should be rate limited.
        
        Returns: (is_limited, current_count, remaining)
        """
        limit = limit or self.default_limit
        window = window or self.default_window
        
        redis_client = self._get_redis()
        if redis_client is None:
            # If Redis is not available, allow request but log warning
            return (False, 0, limit)
        
        try:
            pipe = redis_client.pipeline()
            now = int(time.time())
            window_key = f"ratelimit:{key}:{now // window}"
            
            pipe.incr(window_key)
            pipe.expire(window_key, window)
            results = pipe.execute()
            
            current_count = results[0]
            remaining = max(0, limit - current_count)
            is_limited = current_count > limit
            
            return (is_limited, current_count, remaining)
        except Exception:
            # On Redis error, allow request
            return (False, 0, limit)
    
    def get_client_key(self, request: Request) -> str:
        """Get unique key for rate limiting based on client IP or user"""
        # Try to get user ID from request state (if authenticated)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        
        return f"ip:{ip}"


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next: Callable):
    """FastAPI middleware for rate limiting"""
    # Skip rate limiting for health checks
    if request.url.path in ["/health", "/healthz", "/ready", "/metrics"]:
        return await call_next(request)
    
    client_key = rate_limiter.get_client_key(request)
    endpoint_key = f"{client_key}:{request.url.path}"
    
    is_limited, count, remaining = rate_limiter.is_rate_limited(endpoint_key)
    
    if is_limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "retry_after": rate_limiter.default_window
            },
            headers={
                "X-RateLimit-Limit": str(rate_limiter.default_limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + rate_limiter.default_window),
                "Retry-After": str(rate_limiter.default_window)
            }
        )
    
    response = await call_next(request)
    
    # Add rate limit headers to response
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.default_limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(
        int(time.time()) + rate_limiter.default_window
    )
    
    return response


def rate_limit(limit: int = 100, window: int = 60):
    """
    Decorator for rate limiting specific endpoints.
    
    Usage:
        @app.get("/api/expensive")
        @rate_limit(limit=10, window=60)
        async def expensive_endpoint():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            client_key = rate_limiter.get_client_key(request)
            endpoint_key = f"{client_key}:{func.__name__}"
            
            is_limited, count, remaining = rate_limiter.is_rate_limited(
                endpoint_key, limit=limit, window=window
            )
            
            if is_limited:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "retry_after": window
                    }
                )
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
