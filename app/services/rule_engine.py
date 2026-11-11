import asyncio
import concurrent.futures
import datetime
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.alert import Alert as AlertModel
from app.schemas.alerts import AlertItem, AlertUpdateRequest, Severity

logger = logging.getLogger("retailiq.rule_engine")


def _run_async(coro: Any) -> Any:
    """Helper to execute an async coroutine synchronously from any context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def compute_alert_idempotency_key(
    video_job_id: str,
    rule_id: str,
    track_id: str,
    alert_type: str,
    event_window: str,
) -> str:
    """Generate deterministic SHA-256 idempotency key:

    SHA256(video_job_id + ":" + rule_id + ":" + track_id + ":" + alert_type + ":" + event_window)
    """
    raw = f"{video_job_id}:{rule_id}:{track_id}:{alert_type}:{event_window}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RuleEngine:
    """Evaluates verified Computer Vision telemetry against operational retail rules

    backed by PostgreSQL persistence with SHA-256 idempotency and duplicate prevention.
    """

    @staticmethod
    def _orm_to_schema(alert_orm: AlertModel) -> AlertItem:
        time_display = (
            alert_orm.time_str
            if alert_orm.time_str
            else alert_orm.created_at.strftime("%H:%M") if alert_orm.created_at else ""
        )
        return AlertItem(
            id=alert_orm.id,
            type=alert_orm.alert_type,
            time=time_display,
            area=alert_orm.area,
            severity=alert_orm.severity,  # type: ignore[arg-type]
            description=alert_orm.description,
            acknowledged=alert_orm.acknowledged,
        )

    async def evaluate_and_persist(
        self,
        cv_data: Dict[str, Any],
        job_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> List[AlertItem]:
        """Evaluate CV telemetry, generate rule-based alerts, and atomically persist

        to PostgreSQL using INSERT ... ON CONFLICT DO NOTHING.
        """
        settings = get_settings()
        now = datetime.datetime.now()
        now_str = now.strftime("%H:%M")

        # Stable job identifier for idempotency computation (uses actual job_id in production)
        effective_key_job_id = job_id or cv_data.get("job_id") or f"eval-{uuid.uuid4().hex[:6]}"

        peak_occupancy = cv_data.get("peak_occupancy", 0)
        avg_dwell_seconds = cv_data.get("average_dwell_seconds", 0.0)
        entries = cv_data.get("entries", 0)
        unique_customers = cv_data.get("unique_customers", 0)
        total_frames = cv_data.get("total_frames", 0)

        job_window = f"f1-f{total_frames}" if total_frames > 0 else "job_summary"

        candidate_alerts: List[Dict[str, Any]] = []

        # Rule 1: Occupancy Critical or Warning Threshold Exceeded
        if peak_occupancy >= settings.ALERT_OCCUPANCY_CRITICAL_THRESHOLD:
            rule_id = "critical_occupancy_rule"
            alert_type = "Critical Store Occupancy"
            track_id = "global"
            idem_key = compute_alert_idempotency_key(
                effective_key_job_id, rule_id, track_id, alert_type, job_window
            )
            candidate_alerts.append({
                "id": f"al-{uuid.uuid4().hex[:8]}",
                "idempotency_key": idem_key,
                "alert_type": alert_type,
                "area": "Main Floor",
                "severity": "critical",
                "description": (
                    f"Peak occupancy reached {peak_occupancy} persons, exceeding critical "
                    f"safety threshold ({settings.ALERT_OCCUPANCY_CRITICAL_THRESHOLD})."
                ),
                "time_str": now_str,
            })
        elif peak_occupancy >= settings.ALERT_OCCUPANCY_WARNING_THRESHOLD:
            rule_id = "warning_occupancy_rule"
            alert_type = "High Store Occupancy"
            track_id = "global"
            idem_key = compute_alert_idempotency_key(
                effective_key_job_id, rule_id, track_id, alert_type, job_window
            )
            candidate_alerts.append({
                "id": f"al-{uuid.uuid4().hex[:8]}",
                "idempotency_key": idem_key,
                "alert_type": alert_type,
                "area": "Main Floor",
                "severity": "warning",
                "description": (
                    f"Peak occupancy reached {peak_occupancy} persons, exceeding warning "
                    f"threshold ({settings.ALERT_OCCUPANCY_WARNING_THRESHOLD})."
                ),
                "time_str": now_str,
            })

        # Rule 2: Store Average Customer Dwell Time Threshold Exceeded
        if avg_dwell_seconds >= settings.ALERT_DWELL_SECONDS_THRESHOLD:
            rule_id = "dwell_time_rule"
            alert_type = "Prolonged Dwell Time"
            track_id = "global"
            idem_key = compute_alert_idempotency_key(
                effective_key_job_id, rule_id, track_id, alert_type, job_window
            )
            candidate_alerts.append({
                "id": f"al-{uuid.uuid4().hex[:8]}",
                "idempotency_key": idem_key,
                "alert_type": alert_type,
                "area": "Department Aisles",
                "severity": "warning",
                "description": (
                    f"Average customer dwell time reached {avg_dwell_seconds:.1f} seconds, "
                    f"exceeding expected threshold ({settings.ALERT_DWELL_SECONDS_THRESHOLD:.0f}s)."
                ),
                "time_str": now_str,
            })

        # Rule 3: High Entrance Traffic Surge
        if entries >= settings.ALERT_ENTRY_SURGE_THRESHOLD or (unique_customers >= 25 and entries >= 10):
            rule_id = "traffic_surge_rule"
            alert_type = "Customer Influx Surge"
            track_id = "global"
            idem_key = compute_alert_idempotency_key(
                effective_key_job_id, rule_id, track_id, alert_type, job_window
            )
            candidate_alerts.append({
                "id": f"al-{uuid.uuid4().hex[:8]}",
                "idempotency_key": idem_key,
                "alert_type": alert_type,
                "area": "Entrance Zone",
                "severity": "info",
                "description": (
                    f"Entrance zone observed a traffic surge with {entries} registered entries "
                    f"and {unique_customers} unique visitors."
                ),
                "time_str": now_str,
            })

        # Rule 4: Individual Customer Prolonged Dwell (when tracking summaries are present)
        for t in cv_data.get("tracking_summaries", []):
            t_dwell = t.get("dwell_seconds", 0.0)
            if t_dwell >= settings.ALERT_DWELL_SECONDS_THRESHOLD:
                rule_id = "track_dwell_rule"
                alert_type = "Prolonged Dwell Time"
                track_id = str(t.get("track_id", 0))
                track_window = f"f{t.get('first_frame', 0)}-f{t.get('last_frame', 0)}"
                idem_key = compute_alert_idempotency_key(
                    effective_key_job_id, rule_id, track_id, alert_type, track_window
                )
                candidate_alerts.append({
                    "id": f"al-{idem_key[:8]}",
                    "idempotency_key": idem_key,
                    "alert_type": alert_type,
                    "area": "Department Aisles",
                    "severity": "warning",
                    "description": (
                        f"Customer track {track_id} observed dwell time of {t_dwell:.1f} seconds, "
                        f"exceeding expected threshold ({settings.ALERT_DWELL_SECONDS_THRESHOLD:.0f}s)."
                    ),
                    "time_str": now_str,
                })

        if not candidate_alerts:
            return []

        async def _persist_all(s: AsyncSession) -> List[AlertItem]:
            # Validate foreign key reference to video_jobs
            db_job_id = None
            candidate_job_id = job_id or cv_data.get("job_id")
            if candidate_job_id:
                from app.models.video import VideoJob as VideoJobModel
                job_check = await s.execute(
                    select(VideoJobModel.id).where(VideoJobModel.id == candidate_job_id)
                )
                if job_check.scalar_one_or_none():
                    db_job_id = candidate_job_id

            for item in candidate_alerts:
                stmt = (
                    pg_insert(AlertModel)
                    .values(
                        id=item["id"],
                        job_id=db_job_id,
                        idempotency_key=item["idempotency_key"],
                        alert_type=item["alert_type"],
                        area=item["area"],
                        severity=item["severity"],
                        description=item["description"],
                        acknowledged=False,
                        time_str=item["time_str"],
                    )
                    .on_conflict_do_nothing(index_elements=["idempotency_key"])
                )
                await s.execute(stmt)

            # Retrieve all candidate alerts from DB by idempotency_key to return complete schemas
            keys = [c["idempotency_key"] for c in candidate_alerts]
            query = select(AlertModel).where(AlertModel.idempotency_key.in_(keys))
            res = await s.execute(query)
            db_records = res.scalars().all()
            return [self._orm_to_schema(r) for r in db_records]

        if session is not None:
            results = await _persist_all(session)
            await session.commit()
            return results

        session_factory = get_session_factory()
        async with session_factory() as s:
            async with s.begin():
                results = await _persist_all(s)
            logger.info(f"Persisted {len(results)} alerts to PostgreSQL for job {effective_key_job_id}")
            return results

    def evaluate_cv_results(
        self,
        cv_data: Dict[str, Any],
        job_id: Optional[str] = None,
    ) -> List[AlertItem]:
        """Synchronous entry point for evaluating CV metrics and persisting alerts."""
        return _run_async(self.evaluate_and_persist(cv_data, job_id=job_id))

    async def list_alerts(
        self,
        severity: Optional[str] = None,
        acknowledged: Optional[bool] = None,
        session: Optional[AsyncSession] = None,
    ) -> List[AlertItem]:
        """List alerts from PostgreSQL filtered by severity and acknowledgment state, newest first."""
        stmt = select(AlertModel).order_by(AlertModel.created_at.desc())
        if severity and severity.lower() != "all":
            stmt = stmt.where(AlertModel.severity == severity.lower())
        if acknowledged is not None:
            stmt = stmt.where(AlertModel.acknowledged == acknowledged)

        if session is not None:
            res = await session.execute(stmt)
            records = res.scalars().all()
            return [self._orm_to_schema(a) for a in records]

        session_factory = get_session_factory()
        async with session_factory() as s:
            res = await s.execute(stmt)
            records = res.scalars().all()
            return [self._orm_to_schema(a) for a in records]

    def list_alerts_sync(
        self,
        severity: Optional[str] = None,
        acknowledged: Optional[bool] = None,
    ) -> List[AlertItem]:
        """Synchronous helper for list_alerts."""
        return _run_async(self.list_alerts(severity=severity, acknowledged=acknowledged))

    async def count_alerts(
        self,
        session: Optional[AsyncSession] = None,
    ) -> Tuple[int, int]:
        """Returns (total_count, unacknowledged_count) directly from PostgreSQL."""
        stmt_total = select(func.count(AlertModel.id))
        stmt_unack = select(func.count(AlertModel.id)).where(AlertModel.acknowledged.is_(False))

        if session is not None:
            total = (await session.execute(stmt_total)).scalar() or 0
            unack = (await session.execute(stmt_unack)).scalar() or 0
            return total, unack

        session_factory = get_session_factory()
        async with session_factory() as s:
            total = (await s.execute(stmt_total)).scalar() or 0
            unack = (await s.execute(stmt_unack)).scalar() or 0
            return total, unack

    async def get_alert(
        self,
        alert_id: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[AlertItem]:
        """Retrieve single alert from PostgreSQL by identifier."""
        if session is not None:
            a = await session.get(AlertModel, alert_id)
            return self._orm_to_schema(a) if a else None

        session_factory = get_session_factory()
        async with session_factory() as s:
            a = await s.get(AlertModel, alert_id)
            return self._orm_to_schema(a) if a else None

    async def update_alert(
        self,
        alert_id: str,
        update_data: AlertUpdateRequest,
        session: Optional[AsyncSession] = None,
    ) -> Optional[AlertItem]:
        """Update an alert's status (acknowledgment / notes) in PostgreSQL."""
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        values: Dict[str, Any] = {
            "acknowledged": update_data.acknowledged,
            "acknowledged_at": now_utc if update_data.acknowledged else None,
        }
        if update_data.notes is not None:
            values["notes"] = update_data.notes

        stmt = update(AlertModel).where(AlertModel.id == alert_id).values(**values)

        if session is not None:
            res = await session.execute(stmt)
            if res.rowcount == 0:
                return None
            await session.commit()
            return await self.get_alert(alert_id, session=session)

        session_factory = get_session_factory()
        async with session_factory() as s:
            async with s.begin():
                res = await s.execute(stmt)
                if res.rowcount == 0:
                    return None
            return await self.get_alert(alert_id, session=s)


_rule_engine: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    """Singleton getter for the rule engine."""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine
