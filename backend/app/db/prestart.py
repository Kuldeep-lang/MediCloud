"""Container prestart: wait for the DB, migrate, then (optionally) seed demo data.

Run as ``python -m app.db.prestart``:
* Docker Compose runs it once in the one-shot ``migrate`` service.
* Kubernetes runs it as an initContainer of every backend pod.

Both migration and seeding happen inside transactions that hold a PostgreSQL
*advisory lock*, so when several replicas start simultaneously exactly one does
the work and the others wait, then find nothing left to do.
"""

import logging
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import engine

logger = logging.getLogger("prestart")

BACKEND_DIR = Path(__file__).resolve().parents[2]
ADVISORY_LOCK_KEY = 7_254_771  # arbitrary, app-wide constant


def wait_for_database(timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database is reachable")
            return
        except Exception as exc:
            if time.monotonic() > deadline:
                logger.error("Database still unreachable after %ss", timeout_seconds)
                raise
            logger.info("Waiting for database... (%s)", type(exc).__name__)
            time.sleep(2)


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False  # keep our logging configuration
    return cfg


def run_migrations() -> None:
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADVISORY_LOCK_KEY})
        cfg = alembic_config()
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    logger.info("Migrations are up to date")


def run_seed() -> None:
    settings = get_settings()
    if not settings.seed_demo_data:
        logger.info("SEED_DEMO_DATA is false - skipping demo data")
        return
    password = settings.seed_demo_password.get_secret_value() if settings.seed_demo_password else ""
    if len(password) < 8:
        raise SystemExit("SEED_DEMO_PASSWORD must be set (min 8 characters) when seeding")

    from app.db.seed import seed_demo_data

    with Session(engine) as session:
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADVISORY_LOCK_KEY})
        created = seed_demo_data(session, password)
        session.commit()
    logger.info("Demo data %s", "created" if created else "already present - nothing to do")


def main() -> None:
    configure_logging(get_settings().log_level)
    wait_for_database()
    run_migrations()
    run_seed()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Prestart failed")
        sys.exit(1)
