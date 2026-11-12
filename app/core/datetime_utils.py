"""Centralized timezone-aware datetime utilities for RetailIQ Backend.

Database timestamps are persisted in UTC (timezone-aware).
Business calendar boundaries (daily/hourly analytics, store-day visitor rollover)
and backend-formatted display fallbacks are evaluated in the configured store
timezone (default: Asia/Kolkata, UTC+05:30).
API ISO-8601 timestamps always carry explicit UTC timezone designators ('Z').
"""

import datetime
from typing import Optional, Tuple
import zoneinfo

from app.core.config import get_settings

DEFAULT_STORE_TIMEZONE = "Asia/Kolkata"


def get_store_timezone(tz_name: Optional[str] = None) -> zoneinfo.ZoneInfo:
    """Resolve the configured IANA store timezone, defaulting to Asia/Kolkata."""
    configured = tz_name or get_settings().STORE_TIMEZONE or DEFAULT_STORE_TIMEZONE
    try:
        return zoneinfo.ZoneInfo(configured)
    except Exception:
        try:
            return zoneinfo.ZoneInfo(DEFAULT_STORE_TIMEZONE)
        except Exception:
            return zoneinfo.ZoneInfo("UTC")


def utc_now() -> datetime.datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc)


def ensure_utc(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """Normalize a datetime to timezone-aware UTC (treating naive values as UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def to_utc_iso(dt: Optional[datetime.datetime]) -> Optional[str]:
    """Serialize a datetime to canonical UTC ISO-8601 format ending with 'Z'."""
    utc_dt = ensure_utc(dt)
    if utc_dt is None:
        return None
    return utc_dt.isoformat().replace("+00:00", "Z")


def to_store_tz(
    dt: Optional[datetime.datetime],
    tz_name: Optional[str] = None,
) -> Optional[datetime.datetime]:
    """Convert a datetime (naive assumed UTC) to the store's IANA timezone."""
    utc_dt = ensure_utc(dt)
    if utc_dt is None:
        return None
    return utc_dt.astimezone(get_store_timezone(tz_name))


def store_now(tz_name: Optional[str] = None) -> datetime.datetime:
    """Return the current datetime converted to the store timezone."""
    return utc_now().astimezone(get_store_timezone(tz_name))


def store_day_bounds_utc(
    tz_name: Optional[str] = None,
    days_offset: int = 0,
    reference_utc: Optional[datetime.datetime] = None,
) -> Tuple[datetime.datetime, datetime.datetime]:
    """Compute UTC [start, end) bounds for a calendar day in the store timezone.

    For Asia/Kolkata (UTC+05:30), local midnight 00:00:00 IST maps to 18:30:00 UTC
    of the previous UTC calendar date.
    """
    tz = get_store_timezone(tz_name)
    ref_utc = ensure_utc(reference_utc) or utc_now()
    local_date = ref_utc.astimezone(tz).date() + datetime.timedelta(days=days_offset)
    local_start = datetime.datetime.combine(local_date, datetime.time.min, tzinfo=tz)
    local_end = local_start + datetime.timedelta(days=1)
    return (
        local_start.astimezone(datetime.timezone.utc),
        local_end.astimezone(datetime.timezone.utc),
    )


def format_store_time_hm(
    dt: Optional[datetime.datetime],
    tz_name: Optional[str] = None,
) -> str:
    """Format a datetime as 'HH:MM' in the store timezone."""
    local_dt = to_store_tz(dt, tz_name=tz_name)
    if local_dt is None:
        return ""
    return local_dt.strftime("%H:%M")


def format_store_uploaded_label(
    dt: Optional[datetime.datetime],
    tz_name: Optional[str] = None,
    reference_utc: Optional[datetime.datetime] = None,
) -> str:
    """Format a video upload timestamp for human display in the store timezone."""
    local_dt = to_store_tz(dt, tz_name=tz_name)
    if local_dt is None:
        local_dt = store_now(tz_name=tz_name)

    tz = get_store_timezone(tz_name)
    ref_local = (ensure_utc(reference_utc) or utc_now()).astimezone(tz)
    today_local = ref_local.date()
    yesterday_local = today_local - datetime.timedelta(days=1)

    hm = local_dt.strftime("%H:%M")
    if local_dt.date() == today_local:
        return f"Today {hm}"
    if local_dt.date() == yesterday_local:
        return f"Yesterday {hm}"
    return local_dt.strftime("%d %b %Y, %H:%M")
