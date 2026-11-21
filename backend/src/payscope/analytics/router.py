from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, HTTPException
from sqlalchemy import func, select

from payscope.analytics.compensation import CompensationFilters, get_compensation_report
from payscope.analytics.insights import InsightFilters, get_salary_insight
from payscope.analytics.schemas import ReportFilters, SalaryReport
from payscope.analytics.service import get_salary_report, get_headcount_report
from payscope.auth.router import require_session
from payscope.database import DatabaseSession
from payscope.models import compensation_packages, countries, employee_salaries, employees

router = APIRouter(
    prefix="/analytics", tags=["Analytics"], dependencies=[Depends(require_session)]
)


@router.get("/headcount")
async def workforce_headcount(filters: Annotated[ReportFilters, Query()], database: DatabaseSession):
    if filters.currency_code:
        raise HTTPException(422, detail="Headcount does not use a currency filter.")
    return await get_headcount_report(database, filters)


@router.get("/compensation")
async def compensation_summary(
    filters: Annotated[CompensationFilters, Query()],
    request: Request,
    response: Response,
    database: DatabaseSession,
):
    report, status = await get_compensation_report(
        database, filters, request.app.state.report_cache
    )
    response.headers["X-Report-Cache"] = status
    return report


@router.get("/salary-insights")
async def salary_insights(
    filters: Annotated[InsightFilters, Query()],
    request: Request,
    response: Response,
    database: DatabaseSession,
) -> dict:
    report, status = await get_salary_insight(
        database, filters, request.app.state.report_cache
    )
    response.headers["X-Report-Cache"] = status
    return report


@router.get("/workforce-overview")
async def workforce_overview(database: DatabaseSession):
    has_package = compensation_packages.c.employee_id.is_not(None)
    has_salary = employee_salaries.c.employee_id.is_not(None)
    rows = await database.execute(
        select(
            countries.c.code.label("country_code"),
            countries.c.name.label("country_name"),
            func.count(employees.c.id).label("employees"),
            func.count(compensation_packages.c.employee_id).label("packages"),
            func.count().filter(~has_package, has_salary).label("salary_only"),
            func.count().filter(~has_package, ~has_salary).label("missing_pay"),
        )
        .select_from(
            employees.join(countries).outerjoin(compensation_packages).outerjoin(employee_salaries)
        )
        .group_by(countries.c.code, countries.c.name)
        .order_by(countries.c.name)
    )
    groups = [dict(row) for row in rows.mappings()]
    return {
        "employees": sum(row["employees"] for row in groups),
        "packages": sum(row["packages"] for row in groups),
        "salary_only": sum(row["salary_only"] for row in groups),
        "missing_pay": sum(row["missing_pay"] for row in groups),
        "countries": groups,
    }


@router.get("/salary-summary")
async def salary_summary(
    filters: Annotated[ReportFilters, Query()],
    request: Request,
    response: Response,
    database: DatabaseSession,
) -> SalaryReport:
    report, cache_status = await get_salary_report(
        database, filters, request.app.state.report_cache
    )
    response.headers["X-Report-Cache"] = cache_status
    return report
