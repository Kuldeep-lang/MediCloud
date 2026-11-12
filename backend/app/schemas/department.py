from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.schemas.common import LongText, ORMModel

DeptName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
DeptCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z]{2,10}$")
]


class DepartmentOut(ORMModel):
    id: int
    name: str
    code: str
    description: str | None
    is_active: bool


class DepartmentCreate(BaseModel):
    name: DeptName
    code: DeptCode
    description: LongText | None = None


class DepartmentUpdate(BaseModel):
    name: DeptName | None = None
    description: LongText | None = None
    is_active: bool | None = None
