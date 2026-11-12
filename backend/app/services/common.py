"""Helpers shared by all services."""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError


def paginate(db: Session, stmt: Select, page: int, page_size: int) -> dict[str, Any]:
    """Run a paginated ORM select and return the standard page envelope."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).unique().all()
    return {"items": list(items), "total": total, "page": page, "page_size": page_size}


def get_or_404[T](db: Session, model: type[T], obj_id: int, label: str | None = None) -> T:
    obj = db.get(model, obj_id)
    if obj is None:
        raise NotFoundError(f"{label or model.__name__} {obj_id} not found")
    return obj


def apply_updates(obj: object, data: dict[str, Any]) -> None:
    for key, value in data.items():
        setattr(obj, key, value)


def like_term(raw: str) -> str:
    """Build a safe ILIKE pattern: user-supplied % and _ are escaped, not wildcards."""
    escaped = raw.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
