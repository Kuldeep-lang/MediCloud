from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate


def list_departments(db: Session, include_inactive: bool = False) -> list[Department]:
    stmt = select(Department).order_by(Department.name)
    if not include_inactive:
        stmt = stmt.where(Department.is_active.is_(True))
    return list(db.scalars(stmt))


def create_department(db: Session, data: DepartmentCreate) -> Department:
    clash = db.scalar(
        select(Department.id).where((Department.name == data.name) | (Department.code == data.code))
    )
    if clash:
        raise ConflictError("A department with this name or code already exists")
    dept = Department(**data.model_dump())
    db.add(dept)
    db.commit()
    return dept


def update_department(db: Session, dept: Department, data: DepartmentUpdate) -> Department:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes:
        clash = db.scalar(
            select(Department.id).where(
                Department.name == changes["name"], Department.id != dept.id
            )
        )
        if clash:
            raise ConflictError("A department with this name already exists")
    for key, value in changes.items():
        setattr(dept, key, value)
    db.commit()
    return dept
