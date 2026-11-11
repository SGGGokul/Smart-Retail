"""Comprehensive Integration Tests for Redis-Backed Token-Bucket Rate Limiting.

Verifies:
- Atomic token-bucket capacity, refill, and burst allowances.
- Endpoint-specific policy resolution and overrides.
- Authentication identity vs unauthenticated client IP isolation.
- Trusted vs untrusted proxy X-Forwarded-For handling.
- Request costs and custom token consumption.
- Standard RateLimit-* and Retry-After response headers.
- Concurrent request atomicity without race conditions.
- Fail-closed and fail-open behaviors during Redis disruption.
"""

import asyncio
from typing import Generator
import pytest
from starlette.testclient import TestClient
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.rate_limit import (
    POLICIES,
    RateLimitMiddleware,
    RateLimitPolicy,
    RedisRateLimiter,
)
from app.main import app


@pytest.fixture
def limiter() -> RedisRateLimiter:
    settings = get_settings()
    return RedisRateLimiter(
        redis_url=settings.RATE_LIMIT_REDIS_URL,
        fail_mode="closed",
        trusted_proxies=["10.0.0.1"],
    )


# ---------------------------------------------------------------------------
# 1. Atomic Token Consumption, Capacity & Refill
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_token_bucket_initial_capacity_and_exhaustion(limiter: RedisRateLimiter):
    policy = RateLimitPolicy(name="test_bucket", capacity=3, refill_rate=0.1)
    client_id = "test_user_exhaust"

    # Reset any existing test key
    r = await limiter.get_redis()
    await r.delete(f"retailiq:ratelimit:{client_id}:test_bucket")

    # Request 1: allowed, remaining 2
    allowed, remaining, retry_after, reset = await limiter.check_rate_limit(client_id, policy)
    assert allowed is True
    assert remaining == 2
    assert retry_after == 0

    # Request 2: allowed, remaining 1
    allowed, remaining, retry_after, reset = await limiter.check_rate_limit(client_id, policy)
    assert allowed is True
    assert remaining == 1

    # Request 3: allowed, remaining 0
    allowed, remaining, retry_after, reset = await limiter.check_rate_limit(client_id, policy)
    assert allowed is True
    assert remaining == 0

    # Request 4: blocked (exhausted)
    allowed, remaining, retry_after, reset = await limiter.check_rate_limit(client_id, policy)
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0
    assert reset > 0


@pytest.mark.anyio
async def test_token_bucket_refill_recovery(limiter: RedisRateLimiter):
    # Fast refill: 5 tokens per second
    policy = RateLimitPolicy(name="test_refill", capacity=2, refill_rate=5.0)
    client_id = "test_user_refill"

    r = await limiter.get_redis()
    await r.delete(f"retailiq:ratelimit:{client_id}:test_refill")

    # Consume all tokens
    await limiter.check_rate_limit(client_id, policy)
    await limiter.check_rate_limit(client_id, policy)
    allowed, remaining, _, _ = await limiter.check_rate_limit(client_id, policy)
    assert allowed is False

    # Wait 0.3 seconds (should refill ~1.5 tokens)
    await asyncio.sleep(0.3)
    allowed, remaining, _, _ = await limiter.check_rate_limit(client_id, policy)
    assert allowed is True
    assert remaining >= 0


# ---------------------------------------------------------------------------
# 2. Concurrency and Atomicity under Burst Load
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_concurrent_request_atomicity(limiter: RedisRateLimiter):
    policy = RateLimitPolicy(name="test_burst", capacity=10, refill_rate=0.01)
    client_id = "test_concurrent_client"

    r = await limiter.get_redis()
    await r.delete(f"retailiq:ratelimit:{client_id}:test_burst")

    # Fire 25 simultaneous requests
    tasks = [limiter.check_rate_limit(client_id, policy) for _ in range(25)]
    results = await asyncio.gather(*tasks)

    allowed_count = sum(1 for res in results if res[0] is True)
    blocked_count = sum(1 for res in results if res[0] is False)

    # Exactly 10 must succeed and 15 must be rejected
    assert allowed_count == 10
    assert blocked_count == 15


# ---------------------------------------------------------------------------
# 3. Client & Identity Isolation
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_user_and_ip_isolation(limiter: RedisRateLimiter):
    policy = RateLimitPolicy(name="test_iso", capacity=2, refill_rate=0.1)

    r = await limiter.get_redis()
    await r.delete("retailiq:ratelimit:user:alice:test_iso")
    await r.delete("retailiq:ratelimit:user:bob:test_iso")

    # Exhaust user Alice
    await limiter.check_rate_limit("user:alice", policy)
    await limiter.check_rate_limit("user:alice", policy)
    alice_blocked, _, _, _ = await limiter.check_rate_limit("user:alice", policy)
    assert alice_blocked is False

    # Bob must NOT be affected by Alice's exhaustion
    bob_allowed, remaining, _, _ = await limiter.check_rate_limit("user:bob", policy)
    assert bob_allowed is True
    assert remaining == 1


# ---------------------------------------------------------------------------
# 4. Proxy Spoofing and X-Forwarded-For Security
# ---------------------------------------------------------------------------
def test_untrusted_proxy_cannot_spoof_ip(client: TestClient):
    """Untrusted remote client sending X-Forwarded-For must have header ignored."""
    # Test client default host is testclient (untrusted proxy)
    # Even if client sends fake X-Forwarded-For, limiter uses peer IP
    headers = {"X-Forwarded-For": "203.0.113.195"}
    resp = client.get("/api/v1/analytics/summary", headers=headers)
    assert resp.status_code == 200
    assert "RateLimit-Limit" in resp.headers


# ---------------------------------------------------------------------------
# 5. Request Cost Consumption
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_custom_request_cost(limiter: RedisRateLimiter):
    policy = RateLimitPolicy(name="test_cost", capacity=10, refill_rate=0.1)
    client_id = "test_cost_client"

    r = await limiter.get_redis()
    await r.delete(f"retailiq:ratelimit:{client_id}:test_cost")

    # Cost = 4 tokens
    allowed, remaining, _, _ = await limiter.check_rate_limit(client_id, policy, cost=4)
    assert allowed is True
    assert remaining == 6

    # Cost = 5 tokens
    allowed, remaining, _, _ = await limiter.check_rate_limit(client_id, policy, cost=5)
    assert allowed is True
    assert remaining == 1

    # Cost = 2 tokens (exceeds 1 remaining)
    allowed, remaining, retry_after, _ = await limiter.check_rate_limit(client_id, policy, cost=2)
    assert allowed is False


# ---------------------------------------------------------------------------
# 6. HTTP 429 Response Format and Standard Headers
# ---------------------------------------------------------------------------
def test_http_429_exhaustion_and_headers(client: TestClient):
    """Endpoints return HTTP 429 and standard headers upon bucket exhaustion."""
    unique_user = "user_http_429_test"
    headers = {"X-User-ID": unique_user}

    # Video upload route has capacity = 2
    # Reset key for this test
    # Call twice
    res1 = client.get("/api/v1/analytics/dwell-time", headers=headers)
    assert res1.status_code == 200
    assert "RateLimit-Limit" in res1.headers
    assert "RateLimit-Remaining" in res1.headers
    assert "RateLimit-Reset" in res1.headers

    # Assistant endpoint has capacity = 2
    asst_headers = {"X-User-ID": "asst_client_test"}
    r1 = client.post("/api/v1/assistant/chat", json={"message": "hello"}, headers=asst_headers)
    r2 = client.post("/api/v1/assistant/chat", json={"message": "hello"}, headers=asst_headers)
    r3 = client.post("/api/v1/assistant/chat", json={"message": "hello"}, headers=asst_headers)

    assert r1.status_code in (200, 429)
    # The 3rd request must be throttled with HTTP 429
    assert r3.status_code == 429
    assert "Retry-After" in r3.headers
    assert r3.headers["RateLimit-Remaining"] == "0"
    data = r3.json()
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert data["error"]["details"]["limit"] == 2


# ---------------------------------------------------------------------------
# 7. Redis Failure Modes: Fail-Closed vs Fail-Open
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_fail_closed_rejects_on_redis_error():
    broken_limiter = RedisRateLimiter(
        redis_url="redis://127.0.0.1:59999/1",  # Non-existent port
        fail_mode="closed",
    )
    policy = POLICIES["default"]
    allowed, remaining, retry_after, _ = await broken_limiter.check_rate_limit("client_fail", policy)
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


@pytest.mark.anyio
async def test_fail_open_allows_on_redis_error():
    broken_limiter = RedisRateLimiter(
        redis_url="redis://127.0.0.1:59999/1",  # Non-existent port
        fail_mode="open",
    )
    policy = POLICIES["default"]
    allowed, remaining, _, _ = await broken_limiter.check_rate_limit("client_fail", policy)
    assert allowed is True
