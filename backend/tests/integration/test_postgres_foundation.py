import asyncio
import os
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from payscope.config import Settings
from payscope.database import create_database_engine
from payscope.main import app
from payscope.models import currencies, employee_salaries, employees, hr_users, report_state
from payscope.seed import DEMO_HR_EMAIL, seed_database

PASSWORD = "integration-test-password"
EDITED_AMOUNT = Decimal("12345.67")


async def require_empty_database() -> None:
    engine = create_database_engine(Settings())
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT to_regnamespace('app') IS NULL")), (
                "TEST_DATABASE_URL must point to a separate, empty PostgreSQL database"
            )
    finally:
        await engine.dispose()


async def check_constraints(connection, employee, salary):
    employee.pop("id")
    salary_update = employee_salaries.update().where(
        employee_salaries.c.employee_id == salary["employee_id"]
    )
    cases = (
        (employees.insert().values(**employee), "23505"),
        (employee_salaries.insert().values(**salary), "23505"),
        (
            employees.insert().values(employee | {"employee_code": "TEST", "country_code": "ZZ"}),
            "23503",
        ),
        (currencies.insert().values(code="JPY", name="Yen", minor_units=2), "23514"),
        (report_state.insert().values(id=2), "23514"),
        (salary_update.values(currency_code="JPY"), "23503"),
        (salary_update.values(annual_gross_base=0), "23514"),
        (salary_update.values(annual_gross_base=1_000_000_000), "22003"),
    )
    for statement, sqlstate in cases:
        with pytest.raises(DBAPIError) as error:
            async with connection.begin_nested():
                await connection.execute(statement)
        assert error.value.orig.sqlstate == sqlstate


async def verify_seed() -> None:
    engine = create_database_engine(Settings())
    revision = select(report_state.c.revision)
    directory = select(employees.c.employee_code, employees.c.id)
    salary_count = select(func.count()).select_from(employee_salaries.join(employees))
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(revision) == 0

        await seed_database(engine, PASSWORD)
        async with engine.begin() as connection:
            ids = dict((await connection.execute(directory)).tuples().all())
            assert set(ids) == {f"EMP-{number:06d}" for number in range(1, 10_001)}
            assert await connection.scalar(salary_count) == 10_000
            assert await connection.scalar(revision) == 1
            password_hash = await connection.scalar(
                select(hr_users.c.password_hash).where(hr_users.c.email == DEMO_HR_EMAIL)
            )
            assert PasswordHasher().verify(password_hash, PASSWORD)
            assert await connection.scalar(select(func.count()).select_from(hr_users)) == 1

            employee_id = ids["EMP-000001"]
            employee = (
                (await connection.execute(employees.select().where(employees.c.id == employee_id)))
                .mappings()
                .one()
            )
            salary = (
                (
                    await connection.execute(
                        employee_salaries.select().where(
                            employee_salaries.c.employee_id == employee_id
                        )
                    )
                )
                .mappings()
                .one()
            )
            await check_constraints(connection, dict(employee), dict(salary))
            edited_salary = employee_salaries.c.employee_id == employee_id
            await connection.execute(
                employee_salaries.update()
                .where(edited_salary)
                .values(annual_gross_base=EDITED_AMOUNT)
            )

        await seed_database(engine, "another-test-password")
        async with engine.begin() as connection:
            assert dict((await connection.execute(directory)).tuples().all()) == ids
            assert await connection.scalar(salary_count) == 10_000
            assert await connection.scalar(revision) == 1
            assert await connection.scalar(select(hr_users.c.password_hash)) == password_hash
            saved_amount = select(employee_salaries.c.annual_gross_base).where(edited_salary)
            assert await connection.scalar(saved_amount) == EDITED_AMOUNT
            await connection.execute(
                employee_salaries.delete().where(
                    employee_salaries.c.employee_id == ids["EMP-000002"]
                )
            )

        await seed_database(engine, PASSWORD)
        async with engine.connect() as connection:
            assert await connection.scalar(salary_count) == 10_000
            assert await connection.scalar(revision) == 2
            assert await connection.scalar(saved_amount) == EDITED_AMOUNT
    finally:
        await engine.dispose()


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is unset")
def test_postgres_foundation(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    asyncio.run(require_empty_database())
    config = Config(Path(__file__).resolve().parents[2] / "alembic.ini")

    command.upgrade(config, "head")
    try:
        command.check(config)
        asyncio.run(verify_seed())
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        command.downgrade(config, "base")
