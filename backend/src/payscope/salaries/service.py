from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.database import advance_report_revision
from payscope.employees.service import missing_employee
from payscope.models import (
    compensation_packages,
    currencies,
    employee_salaries,
    employees,
)
from payscope.salaries.schemas import SalaryResponse, SalaryUpdate

SALARY_COLUMNS = (
    employee_salaries.c.annual_gross_base,
    employee_salaries.c.currency_code,
    employee_salaries.c.updated_at,
)


async def get_salary(database: AsyncSession, employee_id: int) -> SalaryResponse | None:
    result = await database.execute(
        select(*SALARY_COLUMNS)
        .select_from(employees.outerjoin(employee_salaries))
        .where(employees.c.id == employee_id)
    )
    salary = result.mappings().one_or_none()
    if salary is None:
        raise missing_employee()
    if salary["annual_gross_base"] is None:
        return None
    return SalaryResponse.model_validate(salary)


async def save_salary(
    database: AsyncSession, employee_id: int, salary: SalaryUpdate, user_id: UUID
) -> SalaryResponse:
    await database.execute(
        select(employees.c.id).where(employees.c.id == employee_id).with_for_update()
    )
    if await database.scalar(
        select(exists().where(compensation_packages.c.employee_id == employee_id))
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PACKAGE_EXISTS",
                "message": "This employee has a compensation package. Edit it through Compensation instead of replacing the legacy salary.",
            },
        )
    employee_exists, currency_exists = (
        await database.execute(
            select(
                exists().where(employees.c.id == employee_id),
                exists().where(currencies.c.code == salary.currency_code),
            )
        )
    ).one()
    if not employee_exists:
        raise missing_employee()
    if not currency_exists:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "loc": ["body", "currency_code"],
                    "msg": "Currency is unavailable.",
                    "type": "value_error",
                }
            ],
        )

    values = dict(
        annual_gross_base=salary.annual_gross_base,
        currency_code=salary.currency_code,
        updated_by=user_id,
        updated_at=func.clock_timestamp(),
    )
    statement = (
        insert(employee_salaries)
        .values(employee_id=employee_id, **values)
        .on_conflict_do_update(
            index_elements=[employee_salaries.c.employee_id], set_=values
        )
        .returning(*SALARY_COLUMNS)
    )
    result = await database.execute(statement)
    saved = SalaryResponse.model_validate(result.mappings().one())
    await advance_report_revision(database)
    await database.commit()
    return saved
