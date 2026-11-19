from typing import Literal

from redis.exceptions import RedisError
from sqlalchemy import func, null, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.analytics.cache import ReportCache
from payscope.analytics.schemas import ReportFilters, SalaryReport, SalaryStatistics
from payscope.employees.service import employee_dimensions
from payscope.logging import logger
from payscope.models import (
    countries,
    departments,
    employee_salaries,
    employees,
    job_titles,
    report_state,
)

GROUPS = {
    "country": (countries, countries.c.code),
    "department": (departments, departments.c.id),
    "job_title": (job_titles, job_titles.c.id),
}
CURRENT_REVISION = select(report_state.c.revision).where(report_state.c.id == 1)
CacheStatus = Literal["hit", "miss", "bypass"]


def report_query(filters: ReportFilters):
    source = employees.join(employee_salaries)
    group_id, group_name = null(), null()
    if filters.group_by is not None:
        table, group_id = GROUPS[filters.group_by]
        group_name = table.c.name
        source = source.join(table)

    currency = employee_salaries.c.currency_code
    amount = employee_salaries.c.annual_gross_base
    partitions = (currency, group_id)
    ranked = (
        select(
            currency,
            group_id.label("group_id"),
            group_name.label("group_name"),
            amount,
            func.row_number().over(partition_by=partitions, order_by=amount).label("position"),
            func.count().over(partition_by=partitions).label("population"),
        )
        .select_from(source)
        .where(*employee_dimensions(filters))
        .subquery()
    )
    amount = ranked.c.annual_gross_base
    dimensions = (ranked.c.currency_code, ranked.c.group_id, ranked.c.group_name)
    # These positions select the middle row for odd groups and both middle rows for even groups.
    middle = (ranked.c.position * 2).between(ranked.c.population, ranked.c.population + 2)
    statistics = (
        select(
            *dimensions,
            func.count().label("headcount"),
            func.min(amount).label("minimum"),
            func.max(amount).label("maximum"),
            func.sum(amount).label("total_amount"),
            func.avg(amount).filter(middle).label("median"),
        )
        .group_by(*dimensions)
        .subquery()
    )
    revision = CURRENT_REVISION.subquery()
    return select(revision.c.revision, statistics).select_from(
        revision.outerjoin(statistics, true())
    )


async def calculate_report(database: AsyncSession, filters: ReportFilters) -> SalaryReport:
    result = await database.execute(report_query(filters))
    data = result.mappings().all()
    rows = [
        SalaryStatistics(**row, mean=row["total_amount"] / row["headcount"])
        for row in data
        if row["currency_code"] is not None
    ]
    rows.sort(key=lambda row: (row.currency_code, -row.mean, row.group_id))
    return SalaryReport(revision=data[0]["revision"], group_by=filters.group_by, rows=rows)


async def get_salary_report(
    database: AsyncSession, filters: ReportFilters, cache: ReportCache | None
) -> tuple[SalaryReport, CacheStatus]:
    if cache is not None:
        revision = (await database.execute(CURRENT_REVISION)).scalar_one()
        await database.rollback()
        try:
            cached = await cache.get(filters, revision)
        except (RedisError, TimeoutError):
            logger.warning("analytics.cache_read_unavailable")
            cache = None
        else:
            if cached is not None:
                return cached, "hit"

    report = await calculate_report(database, filters)
    await database.rollback()
    if cache is None:
        return report, "bypass"
    try:
        await cache.put(filters, report)
    except (RedisError, TimeoutError):
        logger.warning("analytics.cache_write_unavailable")
    return report, "miss"
