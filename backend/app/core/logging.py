import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Log to stdout (container-friendly: collected by Docker / Kubernetes)."""
    logging.basicConfig(
        level=level.upper(),
        stream=sys.stdout,
        format="%(asctime)s %(levelname)-7s %(name)s - %(message)s",
        force=True,
    )
    for noisy in ("sqlalchemy.engine", "alembic.runtime.plugins"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
