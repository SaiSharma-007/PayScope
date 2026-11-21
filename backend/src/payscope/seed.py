import argparse
import asyncio
from collections.abc import Iterable
from typing import Any
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from sqlalchemy import ColumnElement, Table, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from payscope.config import SeedSettings, Settings
from payscope.database import advance_report_revision, create_database_engine
from payscope.logging import configure_logging, log_failure, logger
from payscope.models import (
    countries,
    currencies,
    departments,
    employee_salaries,
    employees,
    hr_users,
    job_titles,
)
from payscope.seed_data import (
    CURRENCIES,
    DEPARTMENTS,
    EMPLOYEE_COUNT,
    LOCATIONS,
    generate_employees,
)

DEMO_HR_EMAIL = "hr@payscope.example"


async def insert_missing(
    connection: AsyncConnection,
    table: Table,
    key: ColumnElement,
    rows: list[dict[str, Any]],
) -> bool:
    statement = insert(table).on_conflict_do_nothing(index_elements=[key])
    result = await connection.execute(statement.returning(literal_column("1")), rows)
    return result.first() is not None


async def seed_lookup(
    connection: AsyncConnection, table: Table, names: Iterable[str]
) -> tuple[dict[str, int], bool]:
    normalized_name = func.lower(table.c.name)
    changed = await insert_missing(
        connection, table, normalized_name, [{"name": name} for name in names]
    )
    result = await connection.execute(select(normalized_name, table.c.id))
    return {name: lookup_id for name, lookup_id in result}, changed


async def seed_hr_user(connection: AsyncConnection, password: str) -> UUID:
    demo_account = hr_users.c.email == DEMO_HR_EMAIL
    query = select(hr_users.c.id, hr_users.c.manage_agent_prompts, hr_users.c.view_agent_observability).where(demo_account)
    user = (await connection.execute(query)).one_or_none()
    if user is not None:
        if not user.manage_agent_prompts or not user.view_agent_observability:
            await connection.execute(
                hr_users.update().where(demo_account).values(manage_agent_prompts=True, view_agent_observability=True)
            )
        return user.id

    await insert_missing(
        connection,
        hr_users,
        hr_users.c.email,
        [
            {
                "id": uuid4(),
                "email": DEMO_HR_EMAIL,
                "display_name": "HR Manager",
                "manage_agent_prompts": True,
                "view_agent_observability": True,
                "password_hash": await asyncio.to_thread(
                    PasswordHasher().hash, password
                ),
            }
        ],
    )
    return (await connection.execute(query)).scalar_one()


async def seed_database(engine: AsyncEngine, password: str) -> None:
    demo_employees = list(generate_employees())
    async with engine.begin() as connection:
        user_id = await seed_hr_user(connection, password)
        countries_changed = await insert_missing(
            connection,
            countries,
            countries.c.code,
            [
                {"code": code, "name": location.country}
                for code, location in LOCATIONS.items()
            ],
        )
        currencies_changed = await insert_missing(
            connection,
            currencies,
            currencies.c.code,
            [
                {"code": code, "name": name, "minor_units": 2}
                for code, name in CURRENCIES.items()
            ],
        )
        department_ids, departments_changed = await seed_lookup(
            connection, departments, DEPARTMENTS
        )
        titles = dict.fromkeys(
            title for roles in DEPARTMENTS.values() for title in roles
        )
        title_ids, titles_changed = await seed_lookup(connection, job_titles, titles)

        employees_changed = await insert_missing(
            connection,
            employees,
            employees.c.employee_code,
            [
                {
                    "employee_code": employee.code,
                    "full_name": employee.name,
                    "country_code": employee.country,
                    "department_id": department_ids[employee.department.lower()],
                    "job_title_id": title_ids[employee.job_title.lower()],
                }
                for employee in demo_employees
            ],
        )
        result = await connection.execute(
            select(employees.c.employee_code, employees.c.id).where(
                employees.c.employee_code.in_(
                    [employee.code for employee in demo_employees]
                )
            )
        )
        employee_ids = {code: employee_id for code, employee_id in result}
        salaries_changed = await insert_missing(
            connection,
            employee_salaries,
            employee_salaries.c.employee_id,
            [
                {
                    "employee_id": employee_ids[employee.code],
                    "annual_gross_base": employee.annual_gross_base,
                    "currency_code": employee.currency,
                    "updated_by": user_id,
                }
                for employee in demo_employees
            ],
        )

        if any(
            (
                countries_changed,
                currencies_changed,
                departments_changed,
                titles_changed,
                employees_changed,
                salaries_changed,
            )
        ):
            await advance_report_revision(connection)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed fictional PayScope employees and compensation."
    )
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--compensation",
        choices=["preview", "apply"],
        help="Reframe missing demo packages, preserving each recorded total.",
    )
    operation.add_argument(
        "--equity",
        choices=["preview", "apply"],
        help="Preview or populate fictional equity for saved demo packages.",
    )
    operation.add_argument(
        "--demo-history",
        choices=["preview", "apply"],
        help="Add historical allocations and targets to untouched legacy demo data.",
    )
    arguments = parser.parse_args()
    if arguments.equity or arguments.demo_history:
        from payscope.compensation.demo_history import upgrade_demo_history
        from payscope.compensation.equity_seed import seed_equity

        engine = create_database_engine(Settings())
        try:
            seed, mode = (
                (upgrade_demo_history, arguments.demo_history)
                if arguments.demo_history
                else (seed_equity, arguments.equity)
            )
            result = await seed(engine, apply=mode == "apply")
            logger.info("seed.%s mode=%s counts=%s", seed.__name__, mode, result)
        finally:
            await engine.dispose()
        return
    settings = SeedSettings()
    engine = create_database_engine(settings)
    try:
        logger.info("seed.started employees=%d", EMPLOYEE_COUNT)
        await seed_database(engine, settings.demo_hr_password.get_secret_value())
        if arguments.compensation:
            from payscope.compensation.seed import seed_compensation

            result = await seed_compensation(
                engine, apply=arguments.compensation == "apply"
            )
            logger.info(
                "seed.compensation eligible=%d created=%d",
                result["eligible"],
                result["created"],
            )
            for country, summary in result["countries"].items():
                logger.info(
                    "seed.compensation.country country=%s employees=%d original_total=%s package_total=%s",
                    country,
                    summary["employees"],
                    summary["original_total"],
                    summary["package_total"],
                )
    finally:
        await engine.dispose()
    logger.info("seed.completed employees=%d", EMPLOYEE_COUNT)


if __name__ == "__main__":
    configure_logging()
    try:
        asyncio.run(main())
    except Exception as exc:
        log_failure("seed.failed", exc)
        raise SystemExit(1) from None
