from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_serializer, field_validator

from payscope.employees.schemas import EmployeeDimensions

Grouping = Literal["country", "department", "job_title"]


class ReportFilters(EmployeeDimensions):
    group_by: Grouping | None = None
    currency_code: Annotated[str, Field(pattern=r"^[A-Za-z]{3}$")] | None = None

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, code: str | None) -> str | None:
        return code.upper() if code is not None else None


class SalaryStatistics(BaseModel):
    group_id: int | str | None
    group_name: str | None
    currency_code: str
    headcount: int
    minimum: Decimal
    maximum: Decimal
    mean: Decimal
    median: Decimal

    @field_serializer("minimum", "maximum", "mean", "median", when_used="json")
    def format_amount(self, amount: Decimal) -> str:
        return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class SalaryReport(BaseModel):
    revision: int
    group_by: Grouping | None
    rows: list[SalaryStatistics]


class HeadcountStatistics(BaseModel):
    group_id: int | str | None
    group_name: str | None
    headcount: int
    currency_code: Literal[""] = ""


class HeadcountReport(BaseModel):
    revision: int
    group_by: Grouping | None
    rows: list[HeadcountStatistics]
