from fastapi import APIRouter, status

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.models import Department
from app.schemas.department import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.services import department_service
from app.services.common import get_or_404

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
def list_departments(_: CurrentUser, db: DbSession, include_inactive: bool = False) -> list:
    return department_service.list_departments(db, include_inactive)


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(body: DepartmentCreate, _: AdminUser, db: DbSession) -> object:
    return department_service.create_department(db, body)


@router.patch("/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int, body: DepartmentUpdate, _: AdminUser, db: DbSession
) -> object:
    dept = get_or_404(db, Department, department_id, "Department")
    return department_service.update_department(db, dept, body)
