import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock

from payscope.analytics.cache import MAX_REPORT_BYTES, ReportCache
from payscope.analytics.schemas import ReportFilters, SalaryReport, SalaryStatistics


def test_report_cache_skips_empty_and_oversized_entries():
    async def check():
        redis = AsyncMock()
        cache = ReportCache(redis, "test")
        filters = ReportFilters()
        report = SalaryReport(revision=1, group_by=None, rows=[])
        await cache.put(filters, report)
        report.rows.append(
            SalaryStatistics(
                group_id=None,
                group_name="x" * MAX_REPORT_BYTES,
                currency_code="USD",
                headcount=2,
                minimum=Decimal("100.00"),
                maximum=Decimal("100.01"),
                mean=Decimal("100.005"),
                median=Decimal("100.005"),
            )
        )
        await cache.put(filters, report)
        redis.set.assert_not_awaited()

    asyncio.run(check())
