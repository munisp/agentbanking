"""
Rate Limiting Service
Redis-based distributed rate limiting with sliding window algorithm

Features:
- Sliding window rate limiting
- Per-endpoint, per-user, per-IP limits
- Distributed rate limiting (Redis)
- Automatic cleanup
- <5ms performance
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json

try:
    import redis.asyncio as redis
except ImportError:
    # Fallback for older redis-py versions
    import redis
    redis.asyncio = redis


logger = logging.getLogger(__name__)


class RateLimiterService:
    """
    Redis-based rate limiting service using sliding window algorithm
    
    Rate Limits:
    - registration: 5 requests/hour per IP
    - login: 10 requests/10min per IP
    - email_verification: 3 requests/hour per user
    - phone_otp: 3 requests/hour per user
    - password_reset: 3 requests/hour per user
    - api_general: 1000 requests/hour per user
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self.redis_url = redis_url
        self.redis_client = None
        
        # Rate limit configurations: {endpoint: {requests, window_seconds}}
        self.limits = {
            "registration": {"requests": 5, "window": 3600},  # 5/hour
            "login": {"requests": 10, "window": 600},  # 10/10min
            "email_verification": {"requests": 3, "window": 3600},  # 3/hour
            "phone_otp": {"requests": 3, "window": 3600},  # 3/hour
            "password_reset": {"requests": 3, "window": 3600},  # 3/hour
            "api_general": {"requests": 1000, "window": 3600},  # 1000/hour
            "kyc_submission": {"requests": 5, "window": 3600},  # 5/hour
            "document_upload": {"requests": 10, "window": 3600},  # 10/hour
        }
    
    async def initialize(self) -> None:
        """Initialize Redis connection"""
        try:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("Rate limiter initialized with Redis")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Rate limiter Redis connection closed")
    
    async def check_rate_limit(
        self,
        endpoint: str,
        identifier: str,  # user_id or IP address
        increment: bool = True
    ) -> Dict[str, Any]:
        """
        Check if request is within rate limit using sliding window algorithm
        
        Args:
            endpoint: Endpoint name (e.g., "registration", "login")
            identifier: User ID or IP address
            increment: Whether to increment counter (default: True)
            
        Returns:
            {
                "allowed": bool,
                "remaining": int,
                "reset_at": float (timestamp),
                "retry_after": int (seconds),
                "limit": int,
                "window": int
            }
        """
        # Check if endpoint has rate limit configured
        if endpoint not in self.limits:
            # No limit configured, allow request
            return {
                "allowed": True,
                "remaining": 999999,
                "reset_at": None,
                "retry_after": 0,
                "limit": None,
                "window": None
            }
        
        config = self.limits[endpoint]
        max_requests = config["requests"]
        window_seconds = config["window"]
        
        # Redis key for this endpoint + identifier
        key = f"ratelimit:{endpoint}:{identifier}"
        
        # Current timestamp
        now = datetime.utcnow().timestamp()
        window_start = now - window_seconds
        
        try:
            # Remove old entries outside the sliding window
            await self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Count requests in current window
            current_count = await self.redis_client.zcard(key)
            
            if current_count < max_requests:
                # Within limit
                if increment:
                    # Add current request to sorted set with timestamp as score
                    await self.redis_client.zadd(key, {str(now): now})
                    
                    # Set expiry on key (cleanup)
                    await self.redis_client.expire(key, window_seconds + 60)
                
                remaining = max_requests - current_count - (1 if increment else 0)
                
                return {
                    "allowed": True,
                    "remaining": remaining,
                    "reset_at": now + window_seconds,
                    "retry_after": 0,
                    "limit": max_requests,
                    "window": window_seconds
                }
            else:
                # Rate limit exceeded
                # Get oldest request timestamp to calculate reset time
                oldest_entries = await self.redis_client.zrange(
                    key, 0, 0, withscores=True
                )
                
                if oldest_entries:
                    oldest_timestamp = oldest_entries[0][1]
                    reset_at = oldest_timestamp + window_seconds
                    retry_after = int(max(reset_at - now, 0))
                else:
                    reset_at = now + window_seconds
                    retry_after = window_seconds
                
                logger.warning(
                    f"Rate limit exceeded for {endpoint}:{identifier} "
                    f"({current_count}/{max_requests})"
                )
                
                return {
                    "allowed": False,
                    "remaining": 0,
                    "reset_at": reset_at,
                    "retry_after": retry_after,
                    "limit": max_requests,
                    "window": window_seconds
                }
        
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # On error, allow request (fail open for availability)
            return {
                "allowed": True,
                "remaining": 0,
                "reset_at": None,
                "retry_after": 0,
                "limit": max_requests,
                "window": window_seconds,
                "error": str(e)
            }
    
    async def reset_limit(self, endpoint: str, identifier: str) -> Dict[str, Any]:
        """
        Reset rate limit for specific endpoint and identifier
        (Admin function)
        
        Args:
            endpoint: Endpoint name
            identifier: User ID or IP address
        """
        key = f"ratelimit:{endpoint}:{identifier}"
        
        try:
            await self.redis_client.delete(key)
            logger.info(f"Rate limit reset for {endpoint}:{identifier}")
            return {"success": True, "message": "Rate limit reset successfully"}
        except Exception as e:
            logger.error(f"Failed to reset rate limit: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_current_usage(
        self,
        endpoint: str,
        identifier: str
    ) -> Dict[str, Any]:
        """
        Get current usage statistics for endpoint and identifier
        
        Args:
            endpoint: Endpoint name
            identifier: User ID or IP address
            
        Returns:
            Usage statistics
        """
        if endpoint not in self.limits:
            return {
                "error": "Unknown endpoint",
                "endpoint": endpoint
            }
        
        config = self.limits[endpoint]
        key = f"ratelimit:{endpoint}:{identifier}"
        
        try:
            now = datetime.utcnow().timestamp()
            window_start = now - config["window"]
            
            # Clean old entries
            await self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Get current count
            current_count = await self.redis_client.zcard(key)
            
            # Get all timestamps in window
            entries = await self.redis_client.zrange(
                key, 0, -1, withscores=True
            )
            
            return {
                "endpoint": endpoint,
                "identifier": identifier,
                "current_usage": current_count,
                "limit": config["requests"],
                "window_seconds": config["window"],
                "remaining": max(0, config["requests"] - current_count),
                "percentage_used": round((current_count / config["requests"]) * 100, 2),
                "requests_timestamps": [
                    datetime.fromtimestamp(score).isoformat()
                    for _, score in entries
                ] if entries else []
            }
        except Exception as e:
            logger.error(f"Failed to get usage statistics: {e}")
            return {
                "error": str(e),
                "endpoint": endpoint,
                "identifier": identifier
            }
    
    async def get_all_limits(self) -> Dict[str, Dict[str, int]]:
        """
        Get all configured rate limits
        
        Returns:
            Dictionary of all rate limit configurations
        """
        return {
            endpoint: {
                "requests": config["requests"],
                "window_seconds": config["window"],
                "window_human": self._format_window(config["window"])
            }
            for endpoint, config in self.limits.items()
        }
    
    def _format_window(self, seconds: int) -> str:
        """Format window duration in human-readable form"""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''}"
        else:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''}"
    
    async def bulk_check(
        self,
        checks: list[Dict[str, str]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Perform multiple rate limit checks in one call
        
        Args:
            checks: List of {"endpoint": str, "identifier": str}
            
        Returns:
            Dictionary of results keyed by "endpoint:identifier"
        """
        results = {}
        
        for check in checks:
            endpoint = check.get("endpoint")
            identifier = check.get("identifier")
            
            if endpoint and identifier:
                key = f"{endpoint}:{identifier}"
                results[key] = await self.check_rate_limit(
                    endpoint, identifier, increment=False
                )
        
        return results


# Example usage and testing
async def example_usage() -> None:
    """Example usage of RateLimiterService"""
    
    # Initialize service
    service = RateLimiterService(redis_url="redis://localhost:6379")
    await service.initialize()
    
    try:
        # Check rate limit for registration
        result = await service.check_rate_limit(
            endpoint="registration",
            identifier="192.168.1.100"
        )
        print(f"Registration rate limit check: {result}")
        
        # Simulate multiple requests
        for i in range(7):
            result = await service.check_rate_limit(
                endpoint="login",
                identifier="user123"
            )
            print(f"Login attempt {i+1}: allowed={result['allowed']}, remaining={result['remaining']}")
            
            if not result['allowed']:
                print(f"Rate limit exceeded! Retry after {result['retry_after']} seconds")
                break
        
        # Get current usage
        usage = await service.get_current_usage("login", "user123")
        print(f"\nCurrent usage: {usage}")
        
        # Get all limits
        all_limits = await service.get_all_limits()
        print(f"\nAll configured limits: {json.dumps(all_limits, indent=2)}")
        
        # Reset limit (admin function)
        reset_result = await service.reset_limit("login", "user123")
        print(f"\nReset result: {reset_result}")
        
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(example_usage())

