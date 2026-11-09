"""Centralized Redis-Backed Token-Bucket Rate Limiting Middleware.

Implements token bucket algorithm via atomic Redis Lua scripting.
Supports endpoint-specific policies, burst allowances, sustained refill rates,
fail-open/fail-closed modes, trusted proxy inspection, and standard rate limit headers.
"""

from dataclasses import dataclass
import logging
import math
from typing import Dict, List, Optional, Tuple
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import get_settings

logger = logging.getLogger("retailiq.rate_limit")

# Atomic Token Bucket Lua script
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
else
    local elapsed = math.max(0, now - last_refill)
    tokens = math.min(capacity, tokens + elapsed * refill_rate)
    last_refill = now
end

local allowed = 0
local retry_after = 0
local remaining = tokens

if tokens >= cost then
    tokens = tokens - cost
    allowed = 1
    remaining = math.floor(tokens)
    retry_after = 0
else
    allowed = 0
    remaining = math.floor(tokens)
    local needed = cost - tokens
    if refill_rate > 0 then
        retry_after = math.ceil(needed / refill_rate)
    else
        retry_after = 60
    end
end

local reset_time = 0
if refill_rate > 0 and tokens < capacity then
    reset_time = math.ceil((capacity - tokens) / refill_rate)
end

local ttl = math.max(60, math.ceil(capacity / (refill_rate > 0 and refill_rate or 1)) * 2)
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
redis.call('EXPIRE', key, ttl)

return {allowed, remaining, retry_after, reset_time}
"""


@dataclass(frozen=True)
class RateLimitPolicy:
    """Token bucket specification for a route or route group."""
    name: str
    capacity: int
    refill_rate: float  # tokens per second
    cost: int = 1


# Predefined Endpoint Policies conforming to specifications
POLICIES: Dict[str, RateLimitPolicy] = {
    # Default Global API: 10 tokens, 1 token/sec refill
    "default": RateLimitPolicy(name="default", capacity=10, refill_rate=1.0),
    # Authentication: 5 tokens, 1 token/12 sec refill
    "auth": RateLimitPolicy(name="auth", capacity=5, refill_rate=1.0 / 12.0),
    # Analytics: 10 tokens, 1 token/sec refill
    "analytics": RateLimitPolicy(name="analytics", capacity=10, refill_rate=1.0),
    # Customer Journey: 10 tokens, 1 token/sec refill
    "customer_journey": RateLimitPolicy(name="customer_journey", capacity=10, refill_rate=1.0),
    # AI Assistant / Groq: 2 tokens, 1 token/10 sec refill
    "assistant": RateLimitPolicy(name="assistant", capacity=2, refill_rate=1.0 / 10.0),
    # RAG Retrieval: 5 tokens, 1 token/5 sec refill
    "rag_retrieval": RateLimitPolicy(name="rag_retrieval", capacity=5, refill_rate=1.0 / 5.0),
    # RAG Ingestion: 1 token, 1 token/10 sec refill
    "rag_ingestion": RateLimitPolicy(name="rag_ingestion", capacity=1, refill_rate=1.0 / 10.0),
    # Video Upload: 2 tokens, 1 token/30 sec refill
    "video_upload": RateLimitPolicy(name="video_upload", capacity=2, refill_rate=1.0 / 30.0),
    # Video Processing: 2 tokens, 1 token/30 sec refill
    "video_processing": RateLimitPolicy(name="video_processing", capacity=2, refill_rate=1.0 / 30.0),
    # Admin Endpoints: 5 tokens, 1 token/5 sec refill
    "admin": RateLimitPolicy(name="admin", capacity=5, refill_rate=1.0 / 5.0),
}


class RedisRateLimiter:
    """Production Redis Token Bucket Rate Limiter."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        fail_mode: Optional[str] = None,
        trusted_proxies: Optional[List[str]] = None,
    ) -> None:
        settings = get_settings()
        self.redis_url = redis_url or settings.RATE_LIMIT_REDIS_URL
        self.fail_mode = (fail_mode or settings.RATE_LIMIT_FAIL_MODE).lower()
        self.trusted_proxies = set(trusted_proxies or settings.RATE_LIMIT_TRUSTED_PROXIES)
        self._redis: Optional[aioredis.Redis] = None
        self._script_sha: Optional[str] = None

    async def get_redis(self) -> aioredis.Redis:
        """Obtain or initialize Redis client pool with RESP2 compatibility."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url,
                protocol=2,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
        return self._redis

    async def _get_script_sha(self, r: aioredis.Redis) -> str:
        """Cache or load Lua script SHA in Redis."""
        if self._script_sha is None:
            self._script_sha = await r.script_load(TOKEN_BUCKET_LUA)
        return self._script_sha

    def extract_client_identifier(self, request: Request) -> str:
        """Securely extract client identifier from request.
        
        Prioritizes authenticated user ID over IP address.
        Never trusts arbitrary X-Forwarded-For headers unless connection originates
        from a configured trusted proxy.
        """
        # 1. Authenticated user ID (from headers or auth state)
        req_state = getattr(request, "state", None)
        user_id = request.headers.get("x-user-id") or (getattr(req_state, "user_id", None) if req_state else None)
        if user_id:
            return f"user:{user_id}"

        # 2. Remote peer IP address
        peer_ip = request.client.host if request.client else "127.0.0.1"

        # 3. Inspect X-Forwarded-For only if peer is trusted proxy
        if peer_ip in self.trusted_proxies:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                # Take leftmost client IP
                client_ip = forwarded.split(",")[0].strip()
                return f"ip:{client_ip}"

        return f"ip:{peer_ip}"

    def resolve_policy(self, request: Request) -> RateLimitPolicy:
        """Determine endpoint-specific rate limit policy."""
        path = request.url.path
        method = request.method.upper()

        if path.startswith("/api/v1/auth"):
            return POLICIES["auth"]
        elif path.startswith("/api/v1/analytics"):
            return POLICIES["analytics"]
        elif path.startswith("/api/v1/customer-journey"):
            return POLICIES["customer_journey"]
        elif path.startswith("/api/v1/assistant"):
            return POLICIES["assistant"]
        elif path.startswith("/api/v1/rag/ingest"):
            return POLICIES["rag_ingestion"]
        elif path.startswith("/api/v1/rag"):
            return POLICIES["rag_retrieval"]
        elif path == "/api/v1/videos" and method == "POST":
            return POLICIES["video_upload"]
        elif path.startswith("/api/v1/videos/") and ("process" in path or method == "POST"):
            return POLICIES["video_processing"]
        elif path.startswith("/api/v1/admin"):
            return POLICIES["admin"]
        else:
            return POLICIES["default"]

    async def check_rate_limit(
        self,
        client_id: str,
        policy: RateLimitPolicy,
        cost: int = 1,
    ) -> Tuple[bool, int, int, int]:
        """Atomically evaluate rate limit against Redis server time.
        
        Returns:
            (allowed: bool, remaining: int, retry_after: int, reset_time: int)
        """
        key = f"retailiq:ratelimit:{client_id}:{policy.name}"
        try:
            r = await self.get_redis()
            sha = await self._get_script_sha(r)
            sec, usec = await r.time()
            now = sec + usec / 1e6

            result = await r.evalsha(
                sha,
                1,
                key,
                policy.capacity,
                policy.refill_rate,
                cost,
                now,
            )
            allowed = bool(result[0])
            remaining = int(result[1])
            retry_after = int(result[2])
            reset_time = int(result[3])
            return allowed, remaining, retry_after, reset_time

        except Exception as err:
            logger.error(f"Redis rate limit check failed: {err}")
            if self.fail_mode == "open":
                # Fail open: allow traffic but log warning
                logger.warning("Rate limiter failing open due to Redis error.")
                return True, policy.capacity, 0, 0
            else:
                # Fail closed: reject request
                logger.warning("Rate limiter failing closed due to Redis error.")
                return False, 0, 60, 60

    async def close(self) -> None:
        """Close connection pool."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None


_limiter_instance: Optional[RedisRateLimiter] = None


def get_rate_limiter() -> RedisRateLimiter:
    global _limiter_instance
    if _limiter_instance is None:
        _limiter_instance = RedisRateLimiter()
    return _limiter_instance


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI Middleware applying centralized Redis token bucket rate limiting."""

    def __init__(self, app, limiter: Optional[RedisRateLimiter] = None) -> None:
        super().__init__(app)
        self.limiter = limiter or get_rate_limiter()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Bypass internal health check and documentation endpoints from throttling
        path = request.url.path
        if path in {"/health", "/api/v1/health", "/docs", "/redoc", "/openapi.json"}:
            return await call_next(request)

        client_id = self.limiter.extract_client_identifier(request)
        policy = self.limiter.resolve_policy(request)

        # Support custom cost from headers if passed
        cost = 1
        custom_cost = request.headers.get("x-request-cost")
        if custom_cost:
            try:
                cost = max(1, int(custom_cost))
            except ValueError:
                cost = 1

        allowed, remaining, retry_after, reset_time = await self.limiter.check_rate_limit(
            client_id=client_id,
            policy=policy,
            cost=cost,
        )

        if not allowed:
            # Return HTTP 429 Too Many Requests
            headers = {
                "Retry-After": str(retry_after),
                "RateLimit-Limit": str(policy.capacity),
                "RateLimit-Remaining": "0",
                "RateLimit-Reset": str(reset_time),
            }
            error_body = {
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many requests. Please retry after {retry_after} seconds.",
                    "details": {
                        "retryAfter": retry_after,
                        "limit": policy.capacity,
                        "remaining": 0,
                        "reset": reset_time,
                    },
                }
            }
            return JSONResponse(status_code=429, content=error_body, headers=headers)

        response = await call_next(request)

        # Attach rate limiting headers to successful responses
        response.headers["RateLimit-Limit"] = str(policy.capacity)
        response.headers["RateLimit-Remaining"] = str(remaining)
        response.headers["RateLimit-Reset"] = str(reset_time)

        return response
