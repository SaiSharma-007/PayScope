import asyncio
import json
from datetime import date
from decimal import Decimal
from time import perf_counter
from unittest.mock import AsyncMock

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.analytics.cache import MAX_REPORT_BYTES, ReportCache
from payscope.analytics.insights import InsightFilters, get_salary_insight
from payscope.compensation.equity_seed import seed_equity
from payscope.compensation.seed import seed_compensation
from payscope.config import Settings
from payscope.database import create_database_engine
from payscope.models import equity_allocations, report_state
from payscope.seed import seed_database


async def check_seed():
    engine = create_database_engine(Settings())
    entries = {}
    redis = AsyncMock()
    redis.get.side_effect = entries.get
    redis.set.side_effect = lambda key, value, **_: entries.update({key: value})
    cache = ReportCache(redis, "test")
    year = date.today().year

    async def report(insight):
        async with AsyncSession(engine) as session:
            return await get_salary_insight(
                session, InsightFilters(insight=insight, year=year), cache
            )

    async def revision():
        async with engine.connect() as connection:
            return await connection.scalar(select(report_state.c.revision))

    try:
        await seed_database(engine, "isolated-fixture-password")
        assert (await seed_compensation(engine, apply=True))["created"] == 10000
        before, _ = await report("guaranteed_vs_target_ctc")
        prior = await revision()
        preview = await seed_equity(engine)
        assert await revision() == prior
        assert all(currency["eligible"] == 0 for currency in before["currencies"])
        assert await report("guaranteed_vs_target_ctc") == (before, "hit")
        assert await seed_equity(engine, apply=True) == preview
        assert await revision() == prior + 1
        assert preview["no_equity"] > 5000 and preview["awards"] > 1000

        for name in ("guaranteed_vs_target_ctc", "equity_timeline"):
            start = perf_counter()
            result, status = await report(name)
            cold = (perf_counter() - start) * 1000
            assert status == "miss" and result["revision"] == prior + 1
            start = perf_counter()
            assert await report(name) == (result, "hit")
            warm = (perf_counter() - start) * 1000
            size = len(json.dumps(result, separators=(",", ":")).encode())
            assert size <= MAX_REPORT_BYTES and result["employees"] == 10000
            print(f"{name} cold={cold:.1f}ms warm={warm:.1f}ms bytes={size}")
            rows = [
                row for currency in result["currencies"] for row in currency["rows"]
            ]
            if name == "guaranteed_vs_target_ctc":
                assert {row["group_id"] for row in rows} == {
                    "IN",
                    "US",
                    "GB",
                    "DE",
                    "FR",
                }
                assert all(
                    row["eligible"]
                    and Decimal(row["target_ctc"]) > Decimal(row["guaranteed_ctc"])
                    for row in rows
                )
                assert all(
                    sum(row["missing_reasons"].values()) == row["missing"]
                    for row in rows
                )
            else:
                for kind in ("rsu", "option"):
                    assert (
                        len(
                            {
                                row["year"]
                                for row in rows
                                if row["kind"] == kind and row["eligible"]
                            }
                        )
                        >= 3
                    )
                assert any(row["recorded_zero"] for row in rows)
                assert any(row["coverage_status"] == "partial" for row in rows)

        async with engine.begin() as connection:
            allocation = (
                (await connection.execute(select(equity_allocations).limit(1)))
                .mappings()
                .one()
            )
            key = (
                equity_allocations.c.award_id == allocation["award_id"],
                equity_allocations.c.year == allocation["year"],
            )
            await connection.execute(
                equity_allocations.update().where(*key).values(amount=1)
            )
        repeated = await seed_equity(engine, apply=True)
        assert repeated == {
            "no_equity": 0,
            "awards": 0,
            "allocations": 0,
            "unconfigured": preview["unconfigured"],
        }
        assert await revision() == prior + 1
        async with engine.connect() as connection:
            assert (
                await connection.scalar(select(equity_allocations.c.amount).where(*key))
                == 1
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM app.compensation_packages WHERE version = 1"
                    )
                )
                == 10000
            )
    finally:
        await engine.dispose()


def test_populated_demo_and_idempotent_equity_seed(migrated_database):
    asyncio.run(check_seed())
