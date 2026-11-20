import asyncio
from uuid import uuid4

from sqlalchemy import select, text

from payscope.compensation.demo_history import (
    HISTORY_START,
    LEGACY_START,
    upgrade_demo_history,
)
from payscope.compensation.equity_seed import demo_equity
from payscope.compensation.seed import demo_package, demo_version_id
from payscope.config import Settings
from payscope.database import create_database_engine
from payscope.models import (
    compensation_package_components,
    compensation_packages,
    compensation_rule_versions,
    compensation_rules,
    equity_allocations,
    equity_awards,
)
from payscope.seed import seed_database


async def check_upgrade():
    engine = create_database_engine(Settings())
    try:
        await seed_database(engine, "isolated-history-fixture-password")
        version_id = demo_version_id("IN", with_target=False)
        async with engine.begin() as connection:
            user = await connection.scalar(
                text("SELECT id FROM app.hr_users WHERE email = 'hr@payscope.example'")
            )
            rule_id = uuid4()
            await connection.execute(
                compensation_rules.insert().values(
                    id=rule_id,
                    name="Legacy India test",
                    country_code="IN",
                    currency_code="INR",
                    latest_version=1,
                    created_by=user,
                )
            )
            await connection.execute(
                compensation_rule_versions.insert().values(
                    id=version_id,
                    rule_id=rule_id,
                    number=1,
                    name="Legacy India test",
                    created_by=user,
                )
            )
            employees = (
                await connection.execute(
                    text("""
                SELECT e.id AS employee_id, e.employee_code, s.annual_gross_base AS guaranteed_cost
                FROM app.employees e JOIN app.employee_salaries s ON s.employee_id = e.id
                WHERE e.country_code = 'IN' ORDER BY e.employee_code
            """)
                )
            ).mappings()
            examples = []
            for row in employees:
                package = demo_package("IN", row["guaranteed_cost"], LEGACY_START)
                metadata = {
                    "employee_id": row["employee_id"],
                    "updated_by": user,
                    "effective_date": LEGACY_START,
                }
                _, entries = demo_equity(
                    dict(row)
                    | metadata
                    | {
                        "annual_basic_pay": package.annual_basic_pay,
                        "currency_code": "INR",
                    },
                    LEGACY_START,
                )
                if not entries or any(years[0]["year"] != 2026 for _, years in entries):
                    continue
                manual = bool(examples)
                await connection.execute(
                    compensation_packages.insert().values(
                        **metadata,
                        version=1,
                        rule_version_id=version_id,
                        **package.model_dump(exclude={"equity_status", "components"}),
                    )
                )
                await connection.execute(
                    compensation_package_components.insert(),
                    [
                        {
                            "employee_id": row["employee_id"],
                            "position": i,
                            **line.model_dump(exclude={"explanation"}),
                        }
                        for i, line in enumerate(package.components)
                    ],
                )
                for award, years in entries:
                    await connection.execute(
                        equity_awards.insert(), award | {"version": 2 if manual else 1}
                    )
                    await connection.execute(equity_allocations.insert(), years)
                examples.append((row, entries))
                if len(examples) == 2:
                    break
        [(original, entries), (untouched, _)] = examples
        preview = await upgrade_demo_history(engine)
        assert preview["packages"] == 1 and preview["skipped"] == 1
        assert (
            preview["awards"] == len(entries) and preview["historical_allocations"] >= 2
        )
        assert await upgrade_demo_history(engine, apply=True) == preview
        assert (await upgrade_demo_history(engine, apply=True))["packages"] == 0
        async with engine.connect() as connection:
            result = await connection.execute(
                select(compensation_packages).where(
                    compensation_packages.c.employee_id.in_(
                        [original["employee_id"], untouched["employee_id"]]
                    )
                )
            )
            packages = {row["employee_id"]: row for row in result.mappings()}
            upgraded = packages[original["employee_id"]]
            assert (
                upgraded["effective_date"] == HISTORY_START and upgraded["version"] == 2
            )
            assert (
                upgraded["guaranteed_cost"]
                == original["guaranteed_cost"]
                < upgraded["target_cost"]
            )
            assert packages[untouched["employee_id"]]["effective_date"] == LEGACY_START
            for award, years in entries:
                result = await connection.execute(
                    select(equity_allocations).where(
                        equity_allocations.c.award_id == award["id"]
                    )
                )
                amounts = {row["year"]: row["amount"] for row in result.mappings()}
                assert len(amounts) > len(years)
                assert all(amounts[row["year"]] == row["amount"] for row in years)
    finally:
        await engine.dispose()


def test_upgrade_demo_history_preserves_existing_pay_and_allocations(migrated_database):
    asyncio.run(check_upgrade())
