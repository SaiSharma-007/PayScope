import asyncio
from unittest.mock import AsyncMock

from payscope.analytics import compensation
from payscope.analytics.cache import REPORT_CACHE_TTL, ReportCache
from redis.exceptions import ConnectionError


def test_report_cache_key_separates_filters_year_and_revision():
    cache = ReportCache(AsyncMock(), "reports")
    filters = compensation.CompensationFilters(country_code="in", year=2026)
    baseline = compensation.report_key(cache, filters, 1)
    normalized = compensation.CompensationFilters(country_code="IN", year=2026)
    assert compensation.report_key(cache, normalized, 1) == baseline
    for key, value in [
        ("year", 2027),
        ("metric", "basic"),
        ("currency_code", "INR"),
        ("group_by", "department"),
    ]:
        assert (
            compensation.report_key(cache, filters.model_copy(update={key: value}), 1)
            != baseline
        )
    assert compensation.report_key(cache, filters, 2) != baseline


def test_compensation_cache_reuses_snapshot_revision_and_falls_back(monkeypatch):
    async def check():
        database = AsyncMock()
        database.scalar.return_value = 7
        redis = AsyncMock()
        redis.get.side_effect = ConnectionError("Unavailable")
        cache = ReportCache(redis, "reports")
        expected = {"revision": 8, "currencies": [{"currency_code": "INR"}]}
        calculate = AsyncMock(return_value=expected)
        monkeypatch.setattr(compensation, "calculate_compensation_report", calculate)
        filters = compensation.CompensationFilters(year=2026)

        report, _ = await compensation.get_compensation_report(database, filters, cache)
        assert report == expected
        assert redis.set.await_args.args[0] == compensation.report_key(
            cache, filters, 8
        )
        assert redis.set.await_args.kwargs == {"ex": REPORT_CACHE_TTL}

        redis.get.side_effect = None
        redis.get.return_value = redis.set.await_args.args[1]
        database.scalar.return_value = 8
        assert await compensation.get_compensation_report(database, filters, cache) == (
            expected,
            "hit",
        )
        calculate.assert_awaited_once()

    asyncio.run(check())
