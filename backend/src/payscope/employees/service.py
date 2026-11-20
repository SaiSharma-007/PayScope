from fastapi import HTTPException
from sqlalchemy import BigInteger, RowMapping, func, literal, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.employees.schemas import (
    CompensationSummary,
    EmployeeDimensions,
    EmployeeFilters,
    EmployeePage,
    EmployeeResponse,
    ReferenceData,
)
from payscope.models import (
    compensation_packages,
    countries,
    currencies,
    departments,
    employee_salaries,
    employees,
    job_titles,
)
from payscope.salaries.schemas import SalaryResponse

EMPLOYEE_DETAILS = select(
    employees.c.id,
    employees.c.employee_code,
    employees.c.full_name,
    employees.c.country_code,
    countries.c.name.label("country_name"),
    employees.c.department_id,
    departments.c.name.label("department_name"),
    employees.c.job_title_id,
    job_titles.c.name.label("job_title"),
    employee_salaries.c.annual_gross_base,
    employee_salaries.c.currency_code,
    employee_salaries.c.updated_at,
    compensation_packages.c.version.label("package_version"),
    compensation_packages.c.annual_basic_pay.label("package_basic"),
    compensation_packages.c.currency_code.label("package_currency"),
    compensation_packages.c.guaranteed_cost.label("package_guaranteed"),
    compensation_packages.c.target_cost.label("package_target"),
).select_from(
    employees.join(countries)
    .join(departments)
    .join(job_titles)
    .outerjoin(employee_salaries)
    .outerjoin(compensation_packages)
)


def missing_employee() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "EMPLOYEE_NOT_FOUND", "message": "Employee not found."},
        headers={"Cache-Control": "no-store"},
    )


def employee_response(row: RowMapping) -> EmployeeResponse:
    salary = (
        SalaryResponse.model_validate(row)
        if row["annual_gross_base"] is not None
        else None
    )
    compensation = (
        CompensationSummary(
            version=row["package_version"],
            annual_basic_pay=row["package_basic"],
            currency_code=row["package_currency"],
            guaranteed_cost=row["package_guaranteed"],
            target_cost=row["package_target"],
        )
        if row["package_version"] is not None
        else None
    )
    return EmployeeResponse(**row, salary=salary, compensation=compensation)


async def list_employees(
    database: AsyncSession, filters: EmployeeFilters
) -> EmployeePage:
    matches = select(employees.c.id).where(*employee_dimensions(filters))
    if filters.search:
        matches = matches.where(
            or_(
                employees.c.full_name.icontains(filters.search, autoescape=True),
                employees.c.employee_code.icontains(filters.search, autoescape=True),
            )
        )
    matching_ids = matches.cte("matching_employees")
    page_ids = (
        select(matching_ids.c.id)
        .order_by(matching_ids.c.id)
        .offset(literal((filters.page - 1) * filters.page_size, BigInteger))
        .limit(filters.page_size)
    )
    page = EMPLOYEE_DETAILS.where(employees.c.id.in_(page_ids)).subquery()
    total = select(func.count().label("total")).select_from(matching_ids).subquery()
    result = await database.execute(
        select(total.c.total, page)
        .select_from(total.outerjoin(page, true()))
        .order_by(page.c.id)
    )
    rows = result.mappings().all()
    return EmployeePage(
        items=[employee_response(row) for row in rows if row["id"] is not None],
        page=filters.page,
        page_size=filters.page_size,
        total=rows[0]["total"],
    )


async def get_employee(database: AsyncSession, employee_id: int) -> EmployeeResponse:
    result = await database.execute(
        EMPLOYEE_DETAILS.where(employees.c.id == employee_id)
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise missing_employee()
    return employee_response(row)


def employee_dimensions(filters: EmployeeDimensions):
    return [
        column == value
        for column, value in (
            (employees.c.country_code, filters.country_code),
            (employees.c.department_id, filters.department_id),
            (employees.c.job_title_id, filters.job_title_id),
        )
        if value is not None
    ]


async def get_reference_data(database: AsyncSession) -> ReferenceData:
    options = {}
    for table in (countries, departments, job_titles, currencies):
        result = await database.execute(select(table).order_by(table.c.name))
        options[table.name] = result.mappings().all()
    return ReferenceData.model_validate(options)
