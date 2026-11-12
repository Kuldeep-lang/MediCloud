"""Database engine and request-scoped sessions."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

# Fail fast when the database is unreachable. Without these, a silent network partition
# (dropped packets) blocks a request on TCP retransmissions for up to ~15 minutes and
# exhausts the worker threadpool. Worst case here is ~7 s (connect 3 s + unacknowledged
# write 4 s), which also keeps a /metrics scrape under Prometheus' 10 s timeout, so an
# outage surfaces as medicloud_db_up=0 (DatabaseDown) rather than a dead API target.
DB_CONNECT_ARGS = {
    "connect_timeout": 3,  # seconds, libpq
    "tcp_user_timeout": 4000,  # ms an unacknowledged write may wait before the socket fails
    "keepalives": 1,  # detect dead idle pooled connections
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}

engine = create_engine(
    _settings.sqlalchemy_url,
    pool_pre_ping=True,  # transparently replace connections dropped by the DB / network
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    pool_recycle=1800,
    pool_timeout=10,  # seconds to wait for a free pooled connection
    connect_args=DB_CONNECT_ARGS,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    with SessionLocal() as session:
        yield session
