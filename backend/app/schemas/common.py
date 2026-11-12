"""Shared schema building blocks."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
)

from app.core.timeutils import ensure_aware


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class Message(BaseModel):
    detail: str


# Money is stored as NUMERIC and validated as Decimal, but serialised to JSON as a
# number so charts and the UI can use it directly.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
MoneyIn = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Phone = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9][0-9 ()\-]{6,18}$"),
]

# Naive datetimes from the UI are interpreted as hospital-local time.
LocalDateTime = Annotated[datetime, AfterValidator(ensure_aware)]
