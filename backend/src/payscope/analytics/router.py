from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from payscope.analytics.schemas import ReportFilters, SalaryReport
from payscope.analytics.service import get_salary_report
from payscope.auth.router import require_session
from payscope.database import DatabaseSession

router = APIRouter(prefix="/analytics", tags=["Analytics"], dependencies=[Depends(require_session)])


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
