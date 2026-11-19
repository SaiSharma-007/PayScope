from typing import Annotated

from fastapi import Path
from pydantic import BaseModel, Field, StringConstraints, field_validator

from payscope.salaries.schemas import SalaryResponse

MAX_DATABASE_ID = 2**63 - 1
EmployeeId = Annotated[int, Path(ge=1, le=MAX_DATABASE_ID)]


class EmployeeDimensions(BaseModel):
    country_code: Annotated[str, Field(pattern=r"^[A-Za-z]{2}$")] | None = None
    department_id: Annotated[int, Field(ge=1, le=MAX_DATABASE_ID)] | None = None
    job_title_id: Annotated[int, Field(ge=1, le=MAX_DATABASE_ID)] | None = None

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, country_code: str | None) -> str | None:
        return country_code.upper() if country_code is not None else None


class EmployeeFilters(EmployeeDimensions):
    search: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""
    page: int = Field(default=1, ge=1, le=2**31 - 1)
    page_size: int = Field(default=25, ge=1, le=100)


class EmployeeResponse(BaseModel):
    id: int
    employee_code: str
    full_name: str
    country_code: str
    country_name: str
    department_id: int
    department_name: str
    job_title_id: int
    job_title: str
    salary: SalaryResponse | None


class EmployeePage(BaseModel):
    items: list[EmployeeResponse]
    page: int
    page_size: int
    total: int


class CodeOption(BaseModel):
    code: str
    name: str


class NamedOption(BaseModel):
    id: int
    name: str


class CurrencyOption(CodeOption):
    minor_units: int


class ReferenceData(BaseModel):
    countries: list[CodeOption]
    departments: list[NamedOption]
    job_titles: list[NamedOption]
    currencies: list[CurrencyOption]
