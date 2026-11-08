"""Shared Fixtures and Test Infrastructure for E2E Tests."""

import asyncio
import inspect
import math
import threading
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
import pytest
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import POLICIES, RateLimitPolicy, RedisRateLimiter
from app.models.customer_journey import CustomerVisitModel, CustomerZoneEventModel
from app.models.rag import RAGChunkModel, RAGDocumentModel
from app.services.visit_service import (
    AtomicSequenceIdGenerator,
    CustomerVisit,
    VisitEvent,
    VisitService,
    VisitStatus,
)
from app.services.zone_service import (
    BoundaryLine,
    CrossingDirection,
    StoreZone,
    ZoneEvent,
    ZoneService,
    ZoneType,
)


def run_sync(coro: Coroutine) -> Any:
    """Safely execute coroutines across environments without depending on OS loopback sockets.

    Executes the coroutine synchronously via direct coroutine driving (stepping),
    avoiding any OS loopback socket creation or event-loop thread deadlocks.
    """
    stack = [coro]
    last_val = None
    is_err = False
    err = None

    while stack:
        top = stack[-1]
        try:
            if is_err:
                is_err = False
                res = top.throw(err)
            else:
                res = top.send(last_val)
            last_val = None
            if inspect.iscoroutine(res) or (hasattr(res, "send") and hasattr(res, "throw")):
                stack.append(res)
        except StopIteration as e:
            stack.pop()
            last_val = e.value
        except Exception as e:
            stack.pop()
            is_err = True
            err = e

    if is_err:
        raise err
    return last_val


class MockRedisConnection:
    """In-memory Redis simulation executing atomic token-bucket operations with virtual time."""

    def __init__(self) -> None:
        self.store: Dict[str, Dict[str, Any]] = {}
        self.virtual_time: float = 1000.0

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        self.store[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                count += 1
        return count

    async def script_load(self, script: str) -> str:
        return "mock_script_sha_12345"

    async def time(self) -> Tuple[int, int]:
        sec = int(self.virtual_time)
        usec = int((self.virtual_time - sec) * 1e6)
        return sec, usec

    async def evalsha(self, sha: str, numkeys: int, key: str, capacity: Any, refill_rate: Any, cost: Any, now: Any) -> List[int]:
        cap = float(capacity)
        refill = float(refill_rate)
        req_cost = float(cost)
        current_time = float(now)

        entry = self.store.get(key)
        if entry is None:
            tokens = cap
            last_refill = current_time
        else:
            tokens = float(entry["tokens"])
            last_refill = float(entry["last_refill"])
            elapsed = max(0.0, current_time - last_refill)
            tokens = min(cap, tokens + elapsed * refill)
            last_refill = current_time

        if tokens >= req_cost:
            tokens -= req_cost
            allowed = 1
            remaining = int(math.floor(tokens))
            retry_after = 0
        else:
            allowed = 0
            remaining = int(math.floor(tokens))
            needed = req_cost - tokens
            retry_after = int(math.ceil(needed / refill)) if refill > 0 else 60

        reset_time = int(math.ceil((cap - tokens) / refill)) if refill > 0 and tokens < cap else 0

        self.store[key] = {
            "tokens": tokens,
            "last_refill": last_refill,
        }
        return [allowed, remaining, retry_after, reset_time]

    async def aclose(self) -> None:
        self.store.clear()


class VirtualRedisLimiter(RedisRateLimiter):
    """Rate limiter utilizing the virtualized in-memory Redis connection."""

    def __init__(self, fail_mode: str = "closed", trusted_proxies: Optional[List[str]] = None) -> None:
        super().__init__(fail_mode=fail_mode, trusted_proxies=trusted_proxies)
        self._mock_conn = MockRedisConnection()

    async def get_redis(self) -> Any:
        return self._mock_conn

    def advance_time(self, seconds: float) -> None:
        """Advance simulated Redis clock by given seconds for deterministic cooldown testing."""
        self._mock_conn.virtual_time += seconds


class MockAsyncSession:
    """In-memory AsyncSession double for testing database persistence layers."""

    def __init__(self) -> None:
        self.visits: Dict[str, CustomerVisitModel] = {}
        self.events: Dict[str, CustomerZoneEventModel] = {}
        self.documents: Dict[str, RAGDocumentModel] = {}
        self.chunks: Dict[str, RAGChunkModel] = {}

    def add(self, entity: Any) -> None:
        if isinstance(entity, CustomerVisitModel):
            self.visits[entity.id] = entity
        elif isinstance(entity, CustomerZoneEventModel):
            self.events[entity.id] = entity
        elif isinstance(entity, RAGDocumentModel):
            self.documents[entity.id] = entity
        elif isinstance(entity, RAGChunkModel):
            self.chunks[entity.id] = entity

    def add_all(self, entities: List[Any]) -> None:
        for e in entities:
            self.add(e)

    async def get(self, model_class: Any, pk: Any) -> Optional[Any]:
        if model_class == CustomerVisitModel:
            return self.visits.get(str(pk))
        elif model_class == CustomerZoneEventModel:
            return self.events.get(str(pk))
        elif model_class == RAGDocumentModel:
            return self.documents.get(str(pk))
        elif model_class == RAGChunkModel:
            return self.chunks.get(str(pk))
        return None

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def close(self) -> None:
        pass


@pytest.fixture
def mock_rate_limiter() -> VirtualRedisLimiter:
    return VirtualRedisLimiter()


@pytest.fixture
def mock_db_session() -> MockAsyncSession:
    return MockAsyncSession()


@pytest.fixture
def store_zones() -> List[StoreZone]:
    """Standard supermarket zone polygons with calibrated ground coordinates."""
    return [
        StoreZone(
            zone_id="zone-entrance",
            name="Entrance Area",
            zone_type=ZoneType.ENTRANCE,
            polygon=[(0.0, 0.0), (200.0, 0.0), (200.0, 100.0), (0.0, 100.0)],
            camera_id="cam-main",
        ),
        StoreZone(
            zone_id="zone-produce",
            name="Produce Section",
            zone_type=ZoneType.DEPARTMENT,
            polygon=[(0.0, 100.0), (200.0, 100.0), (200.0, 300.0), (0.0, 300.0)],
            camera_id="cam-main",
        ),
        StoreZone(
            zone_id="zone-bakery",
            name="Bakery & Deli",
            zone_type=ZoneType.DEPARTMENT,
            polygon=[(200.0, 100.0), (400.0, 100.0), (400.0, 300.0), (200.0, 300.0)],
            camera_id="cam-main",
        ),
        StoreZone(
            zone_id="zone-checkout",
            name="Checkout Counters",
            zone_type=ZoneType.CHECKOUT,
            polygon=[(0.0, 300.0), (400.0, 300.0), (400.0, 400.0), (0.0, 400.0)],
            camera_id="cam-main",
        ),
    ]


@pytest.fixture
def zone_service(store_zones: List[StoreZone]) -> ZoneService:
    service = ZoneService(max_missed_frames=10, min_zone_dwell_seconds=0.2)
    for z in store_zones:
        service.register_zone(z)
    service.register_boundary_line(
        BoundaryLine(
            line_id="line-entrance",
            name="Entrance Boundary",
            p1=(0.0, 20.0),
            p2=(200.0, 20.0),
            camera_id="cam-main",
        )
    )
    service.register_boundary_line(
        BoundaryLine(
            line_id="line-exit",
            name="Exit Boundary",
            p1=(0.0, 380.0),
            p2=(400.0, 380.0),
            camera_id="cam-main",
        )
    )
    return service


@pytest.fixture
def visit_service() -> VisitService:
    service = VisitService(default_timeout_seconds=60.0)
    service.register_entrance_line(line_id="line-entrance", camera_id="cam-main")
    service.register_exit_line(line_id="line-exit", camera_id="cam-main")
    return service
