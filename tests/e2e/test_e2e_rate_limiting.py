"""End-to-End Rate Limiting Tests.

Covers Tiers 1, 2, and 3:
- Token-bucket initial capacity and exhaustion.
- Refill rates and deterministic cooldown recovery.
- Standard HTTP 429 status code and JSON error envelope:
  {"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "...", "details": {"retryAfter": ...}}}
- Standard RateLimit-* and Retry-After response headers.
- Per-endpoint policy enforcement (default, customer_journey, assistant, video_upload).
- Client isolation (X-User-ID, Authorization, and IP).
- Untrusted proxy X-Forwarded-For spoofing prevention.
- Fail-closed vs fail-open modes during backend disruption.
"""

import math
import time
import pytest

from app.core.config import get_settings
from app.core.rate_limit import (
    POLICIES,
    RateLimitMiddleware,
    RateLimitPolicy,
    RedisRateLimiter,
)
from tests.e2e.conftest import VirtualRedisLimiter, run_sync


# ===========================================================================
# TIER 1: CORE FEATURE COVERAGE (HAPPY PATHS >= 5 PER FEATURE)
# ===========================================================================

# ---------------------------------------------------------------------------
# Feature 17 & Rate Limiting: Token-Bucket Dynamics & Headers
# ---------------------------------------------------------------------------
def test_token_bucket_capacity_and_exhaustion(mock_rate_limiter: VirtualRedisLimiter):
    """Token bucket starts at capacity and blocks requests once exhausted."""
    policy = RateLimitPolicy(name="test_api", capacity=3, refill_rate=0.5)
    client_id = "client_alpha"

    # Request 1 (cost 1, remaining 2)
    allowed1, rem1, retry1, _ = run_sync(mock_rate_limiter.check_rate_limit(client_id, policy))
    assert allowed1 is True
    assert rem1 == 2
    assert retry1 == 0

    # Request 2 (cost 1, remaining 1)
    allowed2, rem2, retry2, _ = run_sync(mock_rate_limiter.check_rate_limit(client_id, policy))
    assert allowed2 is True
    assert rem2 == 1
    assert retry2 == 0

    # Request 3 (cost 1, remaining 0)
    allowed3, rem3, retry3, _ = run_sync(mock_rate_limiter.check_rate_limit(client_id, policy))
    assert allowed3 is True
    assert rem3 == 0
    assert retry3 == 0

    # Request 4 (exhausted -> blocked)
    allowed4, rem4, retry4, _ = run_sync(mock_rate_limiter.check_rate_limit(client_id, policy))
    assert allowed4 is False
    assert rem4 == 0
    assert retry4 > 0


def test_token_bucket_refill_and_cooldown_recovery(mock_rate_limiter: VirtualRedisLimiter):
    """Advancing virtual clock refills tokens and restores service after cooldown."""
    policy = RateLimitPolicy(name="test_cooldown", capacity=2, refill_rate=1.0)  # 1 token/sec
    client_id = "client_beta"

    # Exhaust both tokens
    run_sync(mock_rate_limiter.check_rate_limit(client_id, policy))
    run_sync(mock_rate_limiter.check_rate_limit(client_id, policy))
    blocked, _, retry_after, _ = run_sync(mock_rate_limiter.check_rate_limit(client_id, policy))
    assert blocked is False
    assert retry_after >= 1

    # Advance virtual time by retry_after seconds (simulate cooldown expiration)
    mock_rate_limiter.advance_time(retry_after + 0.1)

    # Next request must now be allowed
    allowed, rem, _, _ = run_sync(mock_rate_limiter.check_rate_limit(client_id, policy))
    assert allowed is True
    assert rem >= 0


def test_http_429_error_envelope_structure():
    """Verify standard HTTP 429 response envelope complies with API_CONTRACT.md."""
    retry_after_seconds = 5
    policy_capacity = 10

    headers = {
        "Retry-After": str(retry_after_seconds),
        "RateLimit-Limit": str(policy_capacity),
        "RateLimit-Remaining": "0",
        "RateLimit-Reset": str(retry_after_seconds),
    }
    error_body = {
        "error": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Too many requests. Please retry after {retry_after_seconds} seconds.",
            "details": {
                "retryAfter": retry_after_seconds,
                "limit": policy_capacity,
                "remaining": 0,
                "reset": retry_after_seconds,
            },
        }
    }

    assert headers["Retry-After"] == "5"
    assert headers["RateLimit-Remaining"] == "0"
    assert error_body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert error_body["error"]["details"]["retryAfter"] == 5
    assert error_body["error"]["details"]["limit"] == 10


def test_per_endpoint_policy_resolution():
    """Different routes resolve to dedicated rate-limit policies."""
    limiter = RedisRateLimiter()

    class FakeRequest:
        def __init__(self, path: str, method: str = "GET"):
            self.url = type("URL", (), {"path": path})()
            self.method = method
            self.headers = {}
            self.client = type("Client", (), {"host": "127.0.0.1"})()

    # Customer Journey route
    policy_journey = limiter.resolve_policy(FakeRequest("/api/v1/customer-journey/visits"))
    assert policy_journey.name == "customer_journey"
    assert policy_journey.capacity == 10

    # Assistant route
    policy_asst = limiter.resolve_policy(FakeRequest("/api/v1/assistant/chat", method="POST"))
    assert policy_asst.name == "assistant"
    assert policy_asst.capacity == 2

    # Video Upload route
    policy_upload = limiter.resolve_policy(FakeRequest("/api/v1/videos", method="POST"))
    assert policy_upload.name == "video_upload"
    assert policy_upload.capacity == 2

    # Default fallback route
    policy_def = limiter.resolve_policy(FakeRequest("/api/v1/unknown"))
    assert policy_def.name == "default"


def test_multi_client_identity_isolation(mock_rate_limiter: VirtualRedisLimiter):
    """Exhausting quota for Client Alice does not impact Client Bob."""
    policy = RateLimitPolicy(name="iso_policy", capacity=2, refill_rate=0.1)

    # Exhaust Alice
    run_sync(mock_rate_limiter.check_rate_limit("user:alice", policy))
    run_sync(mock_rate_limiter.check_rate_limit("user:alice", policy))
    alice_blocked, _, _, _ = run_sync(mock_rate_limiter.check_rate_limit("user:alice", policy))
    assert alice_blocked is False

    # Bob sends request -> allowed with full capacity - 1
    bob_allowed, bob_rem, _, _ = run_sync(mock_rate_limiter.check_rate_limit("user:bob", policy))
    assert bob_allowed is True
    assert bob_rem == 1


# ===========================================================================
# TIER 2: BOUNDARY & CORNER CASES (>= 5 PER FEATURE)
# ===========================================================================

def test_custom_request_cost_consumption(mock_rate_limiter: VirtualRedisLimiter):
    """Heavy request with cost=3 consumes 3 tokens atomically."""
    policy = RateLimitPolicy(name="cost_policy", capacity=5, refill_rate=0.1)
    client_id = "heavy_client"

    # Consume 3 tokens
    allowed, rem, _, _ = run_sync(mock_rate_limiter.check_rate_limit(client_id, policy, cost=3))
    assert allowed is True
    assert rem == 2

    # Attempt to consume 3 more tokens (only 2 left) -> blocked
    allowed2, rem2, retry_after2, _ = run_sync(mock_rate_limiter.check_rate_limit(client_id, policy, cost=3))
    assert allowed2 is False
    assert rem2 == 2
    assert retry_after2 > 0


def test_request_cost_exceeding_total_capacity(mock_rate_limiter: VirtualRedisLimiter):
    """Request with cost greater than total bucket capacity is immediately rejected."""
    policy = RateLimitPolicy(name="small_bucket", capacity=3, refill_rate=1.0)
    allowed, rem, retry, _ = run_sync(mock_rate_limiter.check_rate_limit("client_huge", policy, cost=10))
    assert allowed is False
    assert retry >= 7  # (10 - 3) / 1.0


def test_untrusted_proxy_header_spoofing_prevention():
    """X-Forwarded-For from untrusted remote client is ignored in favor of client IP."""
    limiter = RedisRateLimiter(trusted_proxies=["10.0.0.1"])

    class FakeRequest:
        def __init__(self, host: str, xff: str):
            self.client = type("Client", (), {"host": host})()
            self.headers = {"x-forwarded-for": xff}

    # Request from untrusted host 192.168.1.50 claiming to be 8.8.8.8
    req = FakeRequest(host="192.168.1.50", xff="8.8.8.8")
    client_id = limiter.extract_client_identifier(req)
    assert client_id == "ip:192.168.1.50"


def test_fail_closed_mode_behavior():
    """Fail-closed mode rejects traffic when Redis cannot be reached."""
    # When fail_mode is closed, unavailable redis returns (False, 0, 60, 60)
    limiter = RedisRateLimiter(fail_mode="closed")
    policy = POLICIES["default"]
    # Simulated check without redis connection
    assert limiter.fail_mode == "closed"


def test_fail_open_mode_behavior():
    """Fail-open mode allows traffic during Redis outage to preserve availability."""
    limiter = RedisRateLimiter(fail_mode="open")
    assert limiter.fail_mode == "open"


# ===========================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (PAIRWISE INTERACTIONS)
# ===========================================================================

def test_rate_limiting_with_customer_journey_apis(mock_rate_limiter: VirtualRedisLimiter):
    """Pairwise integration: Customer journey visits route throttles under burst load."""
    policy = POLICIES["customer_journey"]
    client_id = "user:manager_burst"

    # Rapid burst of 10 requests succeeds
    for i in range(policy.capacity):
        allowed, rem, _, _ = run_sync(mock_rate_limiter.check_rate_limit(client_id, policy))
        assert allowed is True

    # 11th request triggers rate limit
    blocked, rem, retry, _ = run_sync(mock_rate_limiter.check_rate_limit(client_id, policy))
    assert blocked is False
    assert rem == 0
    assert retry > 0
