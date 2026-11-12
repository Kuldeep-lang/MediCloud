"""Time-zone helpers.

All timestamps are stored in UTC (timestamptz). Business concepts such as
"today's appointments" are evaluated in the hospital's local time zone.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def hospital_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().hospital_timezone)


def now_utc() -> datetime:
    return datetime.now(UTC)


def local_now() -> datetime:
    return datetime.now(hospital_tz())


def local_today() -> date:
    return local_now().date()


def ensure_aware(value: datetime) -> datetime:
    """Interpret naive datetimes as hospital-local time; return a UTC-aware datetime."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=hospital_tz())
    return value.astimezone(UTC)


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC [start, end) bounds of a calendar day in hospital-local time."""
    tz = hospital_tz()
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def local_month_start(today: date | None = None) -> datetime:
    today = today or local_today()
    return datetime.combine(today.replace(day=1), time.min, tzinfo=hospital_tz()).astimezone(UTC)
