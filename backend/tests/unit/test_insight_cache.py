import asyncio
from unittest.mock import AsyncMock

from redis.exceptions import ConnectionError

from payscope.analytics import insights
from payscope.analytics.cache import MAX_REPORT_BYTES, ReportCache
from payscope.analytics.compensation import CompensationFilters, report_key


def test_insight_key_isolates_view_and_normalizes_drill_down():
    cache = ReportCache(AsyncMock(), "reports")

    def key(**params):
        filters = insights.InsightFilters(
            **(
                {"insight": "payroll_concentration", "country_code": "in", "year": 2025}
                | params
            )
        )
        return report_key(cache, filters, 7, insights.INSIGHTS_NAMESPACE)

    baseline = key()
    assert baseline == key(
        country_code="IN", group_by="country", metric="guaranteed", limit=12
    )
    assert baseline != report_key(
        cache, CompensationFilters(country_code="IN", year=2025), 7
    )
    for changes in (
        {"insight": "headcount_vs_payroll"},
        {"department_id": 1},
        {"group_by": "job_title"},
        {"currency_code": "INR"},
        {"metric": "ctc"},
        {"limit": 1},
        {"year": 2026},
    ):
        assert baseline != key(**changes)
    assert key(insight="equity_timeline") != key(
        insight="equity_timeline", start_year=2025
    )


def test_insights_fall_back_for_oversized_cache_and_redis_errors(monkeypatch):
    async def check():
        database = AsyncMock()
        database.scalar.return_value = 7
        redis = AsyncMock()
        redis.get.return_value = b"x" * (MAX_REPORT_BYTES + 1)
        cache = ReportCache(redis, "reports")
        oversized = {"revision": 7, "currencies": [{"label": "x" * MAX_REPORT_BYTES}]}
        calculate = AsyncMock(return_value=oversized)
        monkeypatch.setattr(insights, "calculate_insight", calculate)
        filters = insights.InsightFilters(insight="compensation_mix", year=2025)

        assert await insights.get_salary_insight(database, filters, cache) == (
            oversized,
            "miss",
        )
        redis.set.assert_not_awaited()
        redis.get.side_effect = ConnectionError("Unavailable")
        redis.set.side_effect = ConnectionError("Unavailable")
        calculate.return_value = {
            "revision": 8,
            "currencies": [{"currency_code": "USD"}],
        }
        assert await insights.get_salary_insight(database, filters, cache) == (
            calculate.return_value,
            "miss",
        )
        assert redis.set.await_args.args[0] == report_key(
            cache, filters, 8, insights.INSIGHTS_NAMESPACE
        )
        assert calculate.await_count == 2

    asyncio.run(check())
