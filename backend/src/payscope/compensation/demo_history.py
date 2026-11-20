from datetime import date

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from payscope.compensation.equity_seed import demo_equity
from payscope.compensation.seed import (
    PROFILES,
    demo_package,
    demo_version_id,
    seed_target_rules,
)
from payscope.database import advance_report_revision
from payscope.models import (
    compensation_package_components,
    compensation_packages,
    employee_salaries,
    employees,
    equity_allocations,
    equity_awards,
    hr_users,
)

LEGACY_START = date(2026, 1, 1)
HISTORY_START = date(2022, 1, 1)


async def upgrade_demo_history(engine, *, apply=False):
    legacy_versions = {
        country: demo_version_id(country, with_target=False) for country in PROFILES
    }
    workforce = (
        select(employees.c.id)
        .where(
            employees.c.employee_code.op("~")(r"^EMP-[0-9]{6}$"),
            employees.c.employee_code.between("EMP-000001", "EMP-010000"),
        )
        .order_by(employees.c.id)
    )
    packages = compensation_packages
    async with engine.begin() as connection:
        if apply:
            await connection.execute(text("SELECT pg_advisory_xact_lock(714520019)"))
            await connection.execute(workforce.with_for_update())
        user_id = await connection.scalar(
            select(hr_users.c.id).where(hr_users.c.email == "hr@payscope.example")
        )
        candidates = (
            select(
                employees.c.employee_code,
                employees.c.country_code,
                packages.c.employee_id,
                packages.c.annual_basic_pay,
                packages.c.currency_code,
                packages.c.effective_date,
                packages.c.updated_by,
                packages.c.rule_version_id,
                packages.c.guaranteed_cost,
            )
            .select_from(employees.join(packages).join(employee_salaries))
            .where(
                employees.c.id.in_(workforce),
                packages.c.version == 1,
                packages.c.updated_by == user_id,
                packages.c.effective_date == LEGACY_START,
                packages.c.rule_version_id.in_(legacy_versions.values()),
                packages.c.guaranteed_cost == employee_salaries.c.annual_gross_base,
                packages.c.currency_code == employee_salaries.c.currency_code,
                packages.c.target_cost == packages.c.guaranteed_cost,
            )
        )
        records = (await connection.execute(candidates)).mappings().all()
        awards_by_employee = {}
        existing_awards = await connection.execute(
            select(equity_awards).where(
                equity_awards.c.employee_id.in_(
                    candidates.with_only_columns(packages.c.employee_id)
                )
            )
        )
        for award in existing_awards.mappings():
            awards_by_employee.setdefault(award["employee_id"], []).append(award)

        updates, bonuses, award_updates, history = [], [], [], []
        countries = set()
        skipped = 0
        for record in records:
            employee_id = record["employee_id"]
            country = record["country_code"]
            if record["rule_version_id"] != legacy_versions.get(country):
                skipped += 1
                continue
            _, old_entries = demo_equity(record, LEGACY_START)
            old_awards = {award["id"]: award for award, _ in old_entries}
            saved = awards_by_employee.get(employee_id, [])
            if any(
                award["id"] not in old_awards
                or any(
                    award[key] != value
                    for key, value in old_awards[award["id"]].items()
                )
                for award in saved
            ):
                skipped += 1
                continue
            calculation = demo_package(
                country, record["guaranteed_cost"], HISTORY_START, with_target=True
            )
            if (
                calculation.annual_basic_pay != record["annual_basic_pay"]
                or calculation.currency_code != record["currency_code"]
            ):
                skipped += 1
                continue
            updates.append(
                {
                    "id": employee_id,
                    "target": calculation.target_cost,
                    "rule_version": demo_version_id(country, with_target=True),
                }
            )
            countries.add(country)
            bonuses.append(
                {
                    "employee_id": employee_id,
                    "position": len(calculation.components) - 1,
                    **calculation.components[-1].model_dump(exclude={"explanation"}),
                }
            )
            _, entries = demo_equity(
                dict(record) | {"effective_date": HISTORY_START}, LEGACY_START
            )
            saved_ids = {award["id"] for award in saved}
            for award, years in entries:
                if award["id"] in saved_ids:
                    award_updates.append(
                        {"id": award["id"], "granted": award["grant_date"]}
                    )
                    history.extend(
                        row for row in years if row["year"] < LEGACY_START.year
                    )

        if apply and updates:
            await seed_target_rules(
                connection,
                sorted(countries),
                user_id,
            )
            await connection.execute(
                text("""
                UPDATE app.compensation_packages
                SET effective_date = DATE '2022-01-01', target_cost = :target,
                    rule_version_id = :rule_version, version = version + 1, updated_at = now()
                WHERE employee_id = :id
            """),
                updates,
            )
            await connection.execute(compensation_package_components.insert(), bonuses)
            if award_updates:
                await connection.execute(
                    text("""
                    UPDATE app.equity_awards SET grant_date = :granted,
                        version = version + 1, updated_at = now() WHERE id = :id
                """),
                    award_updates,
                )
                await connection.execute(
                    insert(equity_allocations).on_conflict_do_nothing(), history
                )
            await advance_report_revision(connection)
        return {
            "packages": len(updates),
            "awards": len(award_updates),
            "historical_allocations": len(history),
            "skipped": skipped,
        }
