from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.analytics.cache import ReportCache
from payscope.analytics.compensation import (
    METRIC_COLUMNS,
    CompensationFilters,
    Metric,
    amount,
    compensation_population,
    get_cached_report,
    report_parameters,
)
from payscope.analytics.schemas import Grouping
from payscope.compensation.equity import EQUITY_BY_EMPLOYEE

Insight = Literal[
    "pay_distribution",
    "role_bands",
    "country_comparison",
    "compensation_mix",
    "guaranteed_vs_target_ctc",
    "payroll_concentration",
    "headcount_vs_payroll",
    "equity_timeline",
]
DISTRIBUTIONS = {"pay_distribution", "role_bands", "country_comparison"}
PAYROLL = {"payroll_concentration", "headcount_vs_payroll"}
INSIGHTS_NAMESPACE = "salary-insights:v2"
CTC_EXCLUSIONS = {
    "no_effective_package": "package_id IS NULL",
    "equity_unconfigured": "package_id IS NOT NULL AND NOT equity_configured",
    "missing_allocation": "package_id IS NOT NULL AND equity_configured AND equity_cost IS NULL",
}


class InsightFilters(CompensationFilters):
    model_config = ConfigDict(extra="forbid")

    insight: Insight
    group_by: Grouping | None = None
    metric: Metric | None = None
    limit: int | None = Field(default=None, ge=1, le=25)
    start_year: int | None = Field(default=None, ge=1900, le=9998)

    @model_validator(mode="after")
    def normalize_view(self):
        if self.insight == "equity_timeline":
            if any(
                value is not None for value in (self.metric, self.group_by, self.limit)
            ):
                raise ValueError("Equity timeline uses years and workforce filters.")
            if self.start_year is None:
                self.start_year = max(1900, self.year - 4)
            if not self.year - 19 <= self.start_year <= self.year:
                raise ValueError(
                    "Equity timeline requires a range of 1 to 20 calendar years."
                )
            return self

        if self.start_year is not None:
            raise ValueError("start_year applies only to the equity timeline.")
        fixed_group = {"role_bands": "job_title", "country_comparison": "country"}.get(
            self.insight
        )
        if fixed_group and self.group_by not in (None, fixed_group):
            raise ValueError(f"This insight groups by {fixed_group}.")
        self.group_by = fixed_group or self.group_by or "country"
        self.limit = self.limit or 12

        if self.insight == "guaranteed_vs_target_ctc":
            if self.metric not in (None, "ctc"):
                raise ValueError("The CTC comparison uses the ctc metric.")
            self.metric = "ctc"
        elif self.insight in DISTRIBUTIONS:
            self.metric = self.metric or "basic"
            if self.metric not in {"basic", "ctc", "target_ctc"}:
                raise ValueError("Distribution metrics are basic, ctc, and target_ctc.")
        else:
            self.metric = self.metric or "guaranteed"
            if self.metric not in {"guaranteed", "target", "ctc", "target_ctc"}:
                raise ValueError(
                    "Cost metrics are guaranteed, target, ctc, and target_ctc."
                )
        return self


PERCENTILES = """
    CROSS JOIN LATERAL (
        SELECT json_object_agg('p' || percentile,
                   round(v.ordered_values[floor(position)::int]
                         + (v.ordered_values[ceil(position)::int] - v.ordered_values[floor(position)::int])
                           * (position - floor(position)), 2)::text) AS percentiles
        FROM unnest(ARRAY[10, 25, 50, 75, 90]) AS p(percentile)
        CROSS JOIN LATERAL (
            SELECT 1 + (v.eligible - 1) * p.percentile / 100.0 AS position
        ) AS interpolation
    ) AS distribution
"""

MIX = """
    , component_lines AS (
        SELECT m.currency_code, m.group_id, 'earning' AS category, 'guaranteed' AS commitment,
               'basic_pay' AS code, 'Basic pay' AS label, m.annual_basic_pay AS cost
        FROM included m
        UNION ALL
        SELECT m.currency_code, m.group_id, l.category, l.commitment, l.code, l.label, l.amount
        FROM included m JOIN app.compensation_package_components l ON l.employee_id = m.id
        WHERE l.included_in_cost AND l.category <> 'deduction'
          AND (l.commitment = 'guaranteed' OR :include_target)
        UNION ALL
        SELECT m.currency_code, m.group_id, 'equity', 'guaranteed', 'annual_equity',
               'Annual equity cost', m.equity_cost
        FROM included m WHERE :include_equity
    ), component_totals AS (
        SELECT currency_code, group_id, category, commitment, code, min(label) AS label,
               sum(cost) AS cost
        FROM component_lines GROUP BY currency_code, group_id, category, commitment, code
    ), component_rank AS (
        SELECT *, row_number() OVER (
            PARTITION BY currency_code, group_id ORDER BY cost DESC, category, commitment, code
        ) AS rank
        FROM component_totals
    ), component_buckets AS (
        SELECT currency_code, group_id, category, commitment, CASE WHEN rank <= 16 THEN code END AS code,
               coalesce(min(label) FILTER (WHERE rank <= 16), 'Other components') AS label,
               sum(cost)::text AS amount, count(*) AS component_count
        FROM component_rank GROUP BY currency_code, group_id, category, commitment, 5
    ), components AS (
        SELECT currency_code, group_id,
               json_agg(to_jsonb(b) - 'currency_code' - 'group_id'
                        ORDER BY category, commitment, code) AS lines
        FROM component_buckets b GROUP BY currency_code, group_id
    )
"""

EQUITY_TIMELINE = """
    SELECT p.currency_code, years.year, a.kind, count(*) AS population,
           count(l.amount) AS eligible, count(*) - count(l.amount) AS missing,
           count(*) FILTER (WHERE l.amount = 0) AS recorded_zero,
           sum(l.amount)::text AS amount
    FROM population p
    JOIN app.equity_awards a ON a.employee_id = p.package_id
    CROSS JOIN generate_series(CAST(:start_year AS integer), CAST(:year AS integer)) AS years(year)
    LEFT JOIN app.equity_allocations l ON l.award_id = a.id AND l.year = years.year
                                       AND l.currency_code = p.currency_code
    WHERE a.grant_date < make_date(years.year + 1, 1, 1)
      AND p.effective_date < make_date(years.year + 1, 1, 1)
      AND (a.last_year IS NULL OR a.last_year >= years.year)
    GROUP BY p.currency_code, years.year, a.kind
"""


def grouped_insight_query(filters: InsightFilters) -> str:
    metric = METRIC_COLUMNS[filters.metric]
    aggregates = "sum(value) AS cost"
    fields = "v.cost::text AS amount"
    extra_ctes = ""
    joins = ""
    order = "group_name, group_id"
    if filters.insight in DISTRIBUTIONS:
        aggregates = "array_agg(value ORDER BY value) FILTER (WHERE value IS NOT NULL) AS ordered_values"
        fields = """
            distribution.percentiles,
            (v.ordered_values[v.eligible::int] - v.ordered_values[1])::text AS spread
        """
        joins = PERCENTILES
    elif filters.insight == "guaranteed_vs_target_ctc":
        aggregates = """
            sum(value) AS guaranteed_ctc,
            sum(target_cost + equity_cost) FILTER (WHERE value IS NOT NULL) AS target_ctc
        """
        fields = "v.guaranteed_ctc::text, v.target_ctc::text"
    elif filters.insight in PAYROLL:
        order = "cost DESC NULLS LAST, group_name, group_id"
        fields += ", v.payroll_total"
    elif filters.insight == "compensation_mix":
        extra_ctes = (
            """
            , included AS (
                SELECT m.* FROM measured m JOIN visible v USING (currency_code, group_id)
                WHERE m.value IS NOT NULL
            )
        """
            + MIX
        )
        joins = "LEFT JOIN components c USING (currency_code, group_id)"
        fields += ", coalesce(c.lines, '[]') AS components"
    payroll_total = (
        ", sum(cost) OVER (PARTITION BY currency_code)::text AS payroll_total"
        if filters.insight in PAYROLL
        else ""
    )
    exclusion_counts = ""
    currency_exclusions = ""
    if filters.metric in {"ctc", "target_ctc"}:
        for reason, condition in CTC_EXCLUSIONS.items():
            exclusion_counts += f", count(*) FILTER (WHERE {condition}) AS {reason}"
            currency_exclusions += f", sum({reason}) OVER (PARTITION BY currency_code) AS currency_{reason}"
            fields += f", v.{reason}, v.currency_{reason}"
    return f"""
        , measured AS (
            SELECT *, {metric} AS value FROM population WHERE currency_code IS NOT NULL
        ), grouped AS (
            SELECT currency_code, group_id, group_name, count(*) AS population, count(value) AS eligible,
                   {aggregates}{exclusion_counts}
            FROM measured GROUP BY currency_code, group_id, group_name
        ), ranked AS (
            SELECT *, row_number() OVER (PARTITION BY currency_code ORDER BY {order}) AS position,
                   count(*) OVER (PARTITION BY currency_code) AS group_count,
                   sum(population) OVER (PARTITION BY currency_code) AS currency_population,
                   sum(eligible) OVER (PARTITION BY currency_code) AS currency_eligible
                   {payroll_total}{currency_exclusions}
            FROM grouped
        ), visible AS (
            SELECT * FROM ranked WHERE position <= :limit
        )
        {extra_ctes}, insight_rows AS (
            SELECT v.currency_code, v.position, v.group_count, v.currency_population, v.currency_eligible,
                   v.group_id, v.group_name, v.population, v.eligible, v.population - v.eligible AS missing,
                   {fields}
            FROM visible v {joins}
        )
    """


def insight_query(filters: InsightFilters):
    include_equity = filters.metric in {"ctc", "target_ctc"}
    equity_cte = f"equity AS ({EQUITY_BY_EMPLOYEE}), " if include_equity else ""
    population = compensation_population(
        filters.group_by or "country", include_equity=include_equity
    )
    if filters.insight == "equity_timeline":
        rows = f", insight_rows AS ({EQUITY_TIMELINE})"
        order = "currency_code, year, kind"
    else:
        rows = grouped_insight_query(filters)
        order = "currency_code, position"
    return text(f"""
        WITH {equity_cte}population AS ({population})
        {rows}
        SELECT (SELECT revision FROM app.report_state WHERE id = 1) AS revision,
               (SELECT count(*) FROM population) AS employees,
               (SELECT count(*) FROM population WHERE currency_code IS NULL) AS without_currency,
               (SELECT coalesce(json_agg(insight_rows ORDER BY {order}), '[]') FROM insight_rows) AS rows
    """)


def insight_parameters(filters: InsightFilters) -> dict:
    return report_parameters(filters) | {
        "include_target": filters.metric in {"target", "target_ctc"},
        "include_equity": filters.metric in {"ctc", "target_ctc"},
    }


def share(numerator: Decimal | int, denominator: Decimal | int) -> str | None:
    return amount(Decimal(numerator) * 100 / denominator) if denominator else None


def build_insight_report(snapshot, filters: InsightFilters) -> dict:
    currencies = {}
    for row in snapshot["rows"]:
        code = row.pop("currency_code")
        currency = currencies.setdefault(code, {"currency_code": code, "rows": []})
        if filters.insight == "equity_timeline":
            row["coverage_status"] = (
                "missing"
                if not row["eligible"]
                else "partial"
                if row["missing"]
                else "complete"
            )
        else:
            row.pop("position")
            currency["group_count"] = row.pop("group_count")
            currency["population"] = row.pop("currency_population")
            currency["eligible"] = row.pop("currency_eligible")
            currency["missing"] = currency["population"] - currency["eligible"]
            if filters.metric in {"ctc", "target_ctc"}:
                row["missing_reasons"] = {
                    reason: row.pop(reason) for reason in CTC_EXCLUSIONS
                }
                currency["missing_reasons"] = {
                    reason: row.pop(f"currency_{reason}") for reason in CTC_EXCLUSIONS
                }
        if filters.insight in PAYROLL:
            total = row.pop("payroll_total")
            currency["payroll_total"] = total
            row["headcount_share"] = share(row["population"], currency["population"])
            row["payroll_share"] = (
                share(Decimal(row["amount"]), Decimal(total))
                if row["amount"] is not None and total is not None
                else None
            )
        elif filters.insight == "compensation_mix":
            categories = {}
            for component in row["components"]:
                key = component["category"]
                categories[key] = categories.get(key, Decimal(0)) + Decimal(
                    component["amount"]
                )
            row["categories"] = [
                {"category": key, "amount": amount(total)}
                for key, total in categories.items()
            ]
        currency["rows"].append(row)
    return {
        "revision": snapshot["revision"],
        "insight": filters.insight,
        "year": filters.year,
        "start_year": filters.start_year,
        "metric": filters.metric,
        "group_by": filters.group_by,
        "employees": snapshot["employees"],
        "without_currency": snapshot["without_currency"],
        "currencies": list(currencies.values()),
    }


async def calculate_insight(database: AsyncSession, filters: InsightFilters) -> dict:
    result = await database.execute(insight_query(filters), insight_parameters(filters))
    return build_insight_report(result.mappings().one(), filters)


async def get_salary_insight(
    database: AsyncSession, filters: InsightFilters, cache: ReportCache | None
):
    return await get_cached_report(
        database, filters, cache, calculate_insight, INSIGHTS_NAMESPACE
    )
