import asyncio
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from hashlib import sha256
from typing import Literal

from pydantic import Field
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.analytics.cache import (
    CACHE_TIMEOUT_SECONDS,
    MAX_REPORT_BYTES,
    REPORT_CACHE_TTL,
    ReportCache,
)
from payscope.analytics.schemas import Grouping
from payscope.analytics.service import CURRENT_REVISION
from payscope.compensation.equity import EQUITY_BY_EMPLOYEE, EQUITY_COST
from payscope.compensation.schemas import Currency
from payscope.employees.schemas import EmployeeDimensions
from payscope.logging import logger

Metric = Literal["basic", "guaranteed", "target", "equity", "ctc", "target_ctc"]


class CompensationFilters(EmployeeDimensions):
    currency_code: Currency | None = None
    group_by: Grouping = "country"
    metric: Metric = "guaranteed"
    year: int = Field(default_factory=lambda: date.today().year, ge=1900, le=9998)


def amount(value: Decimal | None) -> str | None:
    return (
        None
        if value is None
        else format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
    )


def report_key(cache: ReportCache, filters: CompensationFilters, revision: int) -> str:
    digest = sha256(filters.model_dump_json().encode()).hexdigest()[:32]
    return f"{cache.prefix}:compensation:v2:{revision}:{digest}"


async def get_compensation_report(
    database: AsyncSession, filters: CompensationFilters, cache: ReportCache | None
):
    if cache:
        revision = await database.scalar(CURRENT_REVISION)
        await database.rollback()
        try:
            async with asyncio.timeout(CACHE_TIMEOUT_SECONDS):
                payload = await cache.redis.get(report_key(cache, filters, revision))
            if payload and len(payload) <= MAX_REPORT_BYTES:
                return json.loads(payload), "hit"
        except (RedisError, TimeoutError, ValueError):
            logger.warning("analytics.compensation_cache_read_unavailable")
    report = await calculate_compensation_report(database, filters)
    await database.rollback()
    if cache and report["currencies"]:
        encoded = json.dumps(report, separators=(",", ":")).encode()
        if len(encoded) <= MAX_REPORT_BYTES:
            try:
                async with asyncio.timeout(CACHE_TIMEOUT_SECONDS):
                    await cache.redis.set(
                        report_key(cache, filters, report["revision"]),
                        encoded,
                        ex=REPORT_CACHE_TTL,
                    )
            except (RedisError, TimeoutError):
                logger.warning("analytics.compensation_cache_write_unavailable")
    return report, "miss" if cache else "bypass"


GROUP_COLUMNS = {
    "country": ("e.country_code", "c.name"),
    "department": ("e.department_id::text", "d.name"),
    "job_title": ("e.job_title_id::text", "j.name"),
}
METRIC_COLUMNS = {
    "basic": "annual_basic_pay",
    "guaranteed": "guaranteed_cost",
    "target": "target_cost",
    "equity": "equity_cost",
    "ctc": "guaranteed_cost + equity_cost",
    "target_ctc": "target_cost + equity_cost",
}


def report_parameters(filters: CompensationFilters) -> dict:
    return filters.model_dump() | {"period_end": date(filters.year + 1, 1, 1)}


async def calculate_compensation_report(
    database: AsyncSession, filters: CompensationFilters
):
    group_id, group_name = GROUP_COLUMNS[filters.group_by]
    metric = METRIC_COLUMNS[filters.metric]
    result = await database.execute(
        text(f"""
        WITH equity AS ({EQUITY_BY_EMPLOYEE}), population AS (
            SELECT e.id, e.country_code, c.name AS country_name,
                   {group_id} AS group_id, {group_name} AS group_name,
                   coalesce(p.currency_code, s.currency_code) AS currency_code,
                   p.employee_id AS package_id, p.annual_basic_pay, p.guaranteed_cost, p.target_cost,
                   {EQUITY_COST} AS equity_cost
            FROM app.employees e
            JOIN app.countries c ON c.code = e.country_code
            JOIN app.departments d ON d.id = e.department_id
            JOIN app.job_titles j ON j.id = e.job_title_id
            LEFT JOIN app.compensation_packages p ON p.employee_id = e.id AND p.effective_date < :period_end
            LEFT JOIN app.employee_salaries s ON s.employee_id = e.id
            LEFT JOIN equity q ON q.employee_id = p.employee_id
            LEFT JOIN app.equity_elections n ON n.employee_id = p.employee_id
            WHERE (CAST(:country_code AS text) IS NULL OR e.country_code = :country_code)
              AND (CAST(:department_id AS bigint) IS NULL OR e.department_id = :department_id)
              AND (CAST(:job_title_id AS bigint) IS NULL OR e.job_title_id = :job_title_id)
              AND (CAST(:currency_code AS text) IS NULL OR coalesce(p.currency_code, s.currency_code) = :currency_code)
        ), measured AS (
            SELECT *, {metric} AS value FROM population WHERE currency_code IS NOT NULL
        ), ranked AS (
            SELECT *, row_number() OVER (PARTITION BY currency_code, group_id ORDER BY value NULLS LAST) AS position,
                   count(value) OVER (PARTITION BY currency_code, group_id) AS eligible
            FROM measured
        ), statistics AS (
            SELECT currency_code, group_id, group_name, count(*) AS population,
                   count(value) AS headcount, min(value)::text AS minimum, max(value)::text AS maximum,
                   avg(value)::text AS mean,
                   (avg(value) FILTER (WHERE position * 2 BETWEEN eligible AND eligible + 2))::text AS median
            FROM ranked GROUP BY currency_code, group_id, group_name
        ), complete AS (
            SELECT * FROM population WHERE package_id IS NOT NULL AND (NOT :include_equity OR equity_cost IS NOT NULL)
        ), coverage AS (
            SELECT country_code, country_name, currency_code, count(*) AS population,
                   count(*) FILTER (WHERE package_id IS NOT NULL AND (NOT :include_equity OR equity_cost IS NOT NULL)) AS eligible,
                   sum(CASE WHEN :include_equity THEN guaranteed_cost + equity_cost ELSE guaranteed_cost END)::text AS total
            FROM population WHERE currency_code IS NOT NULL GROUP BY country_code, country_name, currency_code
        ), component_lines AS (
            SELECT country_code, currency_code, 'earning' AS category, 'basic_pay' AS code,
                   'Basic pay' AS label, annual_basic_pay AS cost FROM complete
            UNION ALL
            SELECT p.country_code, p.currency_code, l.category, l.code, l.label, l.amount
            FROM complete p JOIN app.compensation_package_components l ON l.employee_id = p.id
            WHERE l.included_in_cost AND l.commitment = 'guaranteed' AND l.category <> 'deduction'
            UNION ALL
            SELECT country_code, currency_code, 'equity', 'annual_equity', 'Annual equity cost', equity_cost
            FROM complete WHERE :include_equity
        ), component_totals AS (
            SELECT country_code, currency_code, category, code, min(label) AS label, sum(cost)::text AS amount,
                   count(*) AS recorded, count(*) FILTER (WHERE cost = 0) AS zero
            FROM component_lines GROUP BY country_code, currency_code, category, code
        )
        SELECT (SELECT revision FROM app.report_state WHERE id = 1) AS revision,
               (SELECT count(*) FROM population) AS employees,
               (SELECT count(*) FROM population WHERE package_id IS NULL) AS without_package,
               (SELECT coalesce(json_agg(statistics ORDER BY currency_code, group_name), '[]') FROM statistics) AS statistics,
               (SELECT coalesce(json_agg(coverage ORDER BY country_name, currency_code), '[]') FROM coverage) AS coverage,
               (SELECT coalesce(json_agg(component_totals ORDER BY label, code), '[]') FROM component_totals) AS components
    """),
        report_parameters(filters)
        | {"include_equity": filters.metric in {"equity", "ctc", "target_ctc"}},
    )
    row = result.mappings().one()
    currencies = {}
    for statistic in row["statistics"]:
        currency = statistic.pop("currency_code")
        for field in ("minimum", "median", "maximum", "mean"):
            if statistic[field] is not None:
                statistic[field] = amount(Decimal(statistic[field]))
        currencies.setdefault(currency, []).append(statistic)
    components = {}
    for component in row["components"]:
        key = (component.pop("country_code"), component.pop("currency_code"))
        components.setdefault(key, []).append(component)
    labels = {"earning": "Earnings", "employer_cost": "Employer costs"}
    if filters.metric in {"equity", "ctc", "target_ctc"}:
        labels["equity"] = "Equity"
    for country in row["coverage"]:
        country["components"] = components.get(
            (country["country_code"], country["currency_code"]), []
        )
        totals = dict.fromkeys(labels, Decimal(0))
        for component in country["components"]:
            totals[component["category"]] += Decimal(component["amount"])
        denominator = sum(totals.values())
        country["categories"] = [
            {
                "category": key,
                "label": label,
                "amount": amount(totals[key]),
                "share": amount(totals[key] * 100 / denominator)
                if denominator
                else "0.00",
            }
            for key, label in labels.items()
        ]
    return {
        "revision": row["revision"],
        "year": filters.year,
        "metric": filters.metric,
        "employees": row["employees"],
        "without_package": row["without_package"],
        "currencies": [
            {"currency_code": code, "rows": rows} for code, rows in currencies.items()
        ],
        "composition": row["coverage"],
    }
