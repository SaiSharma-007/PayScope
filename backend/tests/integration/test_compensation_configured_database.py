"""Opt-in .env database checks, with all fixtures confined to a rolled-back transaction."""

import asyncio
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import httpx2
import pytest
from argon2 import PasswordHasher
from payscope.compensation import service
from payscope.config import Settings
from payscope.database import create_database_engine
from payscope.main import app
from payscope.models import (
    compensation_packages,
    compensation_rules,
    departments,
    employee_salaries,
    employees,
    hr_users,
    job_titles,
    report_state,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker


async def check_compensation(monkeypatch):
    settings = Settings()
    engine = create_database_engine(settings)
    user_id = uuid4()
    employee_id = 8_000_000_000 + user_id.int % 1_000_000_000
    token = user_id.hex
    try:
        async with engine.connect() as connection:
            before = await connection.scalar(
                select(func.count()).select_from(employees)
            )
            await connection.rollback()
            transaction = await connection.begin()
            monkeypatch.setattr(app.state, "settings", settings, raising=False)
            monkeypatch.setattr(app.state, "report_cache", None, raising=False)
            monkeypatch.setattr(
                app.state,
                "session_factory",
                async_sessionmaker(
                    connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ),
                raising=False,
            )
            try:
                await connection.execute(
                    hr_users.insert().values(
                        id=user_id,
                        email=f"{token}@example.test",
                        display_name="Compensation test HR",
                        password_hash=PasswordHasher().hash(
                            "compensation-test-password"
                        ),
                    )
                )
                department = await connection.scalar(select(departments.c.id).limit(1))
                title = await connection.scalar(select(job_titles.c.id).limit(1))
                assert department and title, (
                    "Run the base seed before configured-database checks."
                )
                for offset, country in ((0, "IN"), (1, "US")):
                    await connection.execute(
                        employees.insert().values(
                            id=employee_id + offset,
                            employee_code=f"TEST-{token}-{offset}",
                            full_name="Compensation test employee",
                            country_code=country,
                            department_id=department,
                            job_title_id=title,
                        )
                    )
                await connection.execute(
                    employee_salaries.insert().values(
                        employee_id=employee_id,
                        annual_gross_base=Decimal("900000"),
                        currency_code="INR",
                        updated_by=user_id,
                    )
                )
                transport = httpx2.ASGITransport(app=app, raise_app_exceptions=False)
                async with httpx2.AsyncClient(
                    transport=transport, base_url="https://testserver"
                ) as client:
                    base = f"/api/employees/{employee_id}/compensation"
                    rules = "/api/compensation/rules"
                    assert (await client.get(rules)).status_code == 401
                    assert (await client.get(base)).status_code == 401
                    login = await client.post(
                        "/api/auth/sign-in",
                        json={
                            "email": f"{token}@example.test",
                            "password": "compensation-test-password",
                        },
                    )
                    assert login.status_code == 200, login.text
                    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
                    rule = {
                        "name": "Test India",
                        "country_code": "IN",
                        "currency_code": "INR",
                        "components": [
                            {
                                "code": "custom_yearly_bonus",
                                "label": "Custom yearly bonus",
                                "method": "percent_of_base",
                                "value": "1",
                            }
                        ],
                    }
                    assert (await client.post(rules, json=rule)).status_code == 403
                    created = await client.post(rules, headers=headers, json=rule)
                    assert created.status_code == 201, created.text
                    version = created.json()
                    rule_id = version["rule_id"]
                    draft = {
                        "annual_basic_pay": "600000",
                        "currency_code": "INR",
                        "effective_date": date.today().isoformat(),
                        "rule_version_id": version["id"],
                        "overrides": [
                            {
                                "code": "custom_yearly_bonus",
                                "amount": "7000",
                                "reason": "Employee agreement",
                            }
                        ],
                    }
                    assert (await client.get(base)).json() is None
                    assert (
                        await client.put(base, json=draft | {"expected_version": 0})
                    ).status_code == 403
                    preview = await client.post(
                        base + "/preview", headers=headers, json=draft
                    )
                    assert preview.status_code == 200, preview.text
                    assert preview.json()["guaranteed_cost"] == "607000.00"
                    revision = await connection.scalar(select(report_state.c.revision))
                    saved = await client.put(
                        base, headers=headers, json=draft | {"expected_version": 0}
                    )
                    assert saved.status_code == 200, saved.text
                    package = saved.json()
                    assert package["version"] == 1
                    assert package["components"][0]["calculated_amount"] == "6000.00"
                    assert (
                        package["components"][0]["override_reason"]
                        == "Employee agreement"
                    )
                    for field, value in preview.json().items():
                        assert package[field] == value, field
                    assert (
                        await connection.scalar(select(report_state.c.revision))
                        == revision + 1
                    )
                    assert (await client.get(base)).json() == package
                    assert (
                        await client.put(
                            base, headers=headers, json=draft | {"expected_version": 0}
                        )
                    ).status_code == 409
                    legacy = await client.get(f"/api/employees/{employee_id}/salary")
                    assert legacy.json()["annual_gross_base"] == "900000.00"
                    assert (
                        await client.put(
                            f"/api/employees/{employee_id}/salary",
                            headers=headers,
                            json={"annual_gross_base": "1", "currency_code": "INR"},
                        )
                    ).status_code == 409
                    assert (
                        await client.post(
                            f"/api/employees/{employee_id + 1}/compensation/preview",
                            headers=headers,
                            json=draft,
                        )
                    ).status_code == 422
                    assert (
                        await client.post(
                            base + "/preview",
                            headers=headers,
                            json=draft | {"currency_code": "USD"},
                        )
                    ).status_code == 422
                    v2draft = rule | {
                        "expected_version": 1,
                        "components": [rule["components"][0] | {"value": "2"}],
                    }
                    v2 = await client.post(
                        f"{rules}/{rule_id}/versions", headers=headers, json=v2draft
                    )
                    assert v2.status_code == 201, v2.text
                    assert (await client.get(base)).json() == package
                    assert (
                        await client.get(f"/api/compensation/versions/{version['id']}")
                    ).json()["components"][0]["value"] == "1"
                    assert (
                        await client.post(
                            f"{rules}/{rule_id}/versions", headers=headers, json=v2draft
                        )
                    ).status_code == 409
                    assert (
                        await client.patch(
                            f"{rules}/{rule_id}",
                            headers=headers,
                            json={"active": False, "expected_version": 2},
                        )
                    ).status_code == 200
                    assert (
                        await client.post(
                            base + "/preview", headers=headers, json=draft
                        )
                    ).status_code == 200
                    assert (
                        await client.post(
                            base + "/preview",
                            headers=headers,
                            json=draft | {"rule_version_id": v2.json()["id"]},
                        )
                    ).status_code == 422

                    async def fail_revision(_database):
                        raise RuntimeError("Test rollback")

                    with monkeypatch.context() as patch:
                        patch.setattr(service, "advance_report_revision", fail_revision)
                        failed = await client.put(
                            base,
                            headers=headers,
                            json=draft
                            | {"annual_basic_pay": "800000", "expected_version": 1},
                        )
                        assert failed.status_code == 500
                    assert (await client.get(base)).json() == package
                    assert (
                        await connection.scalar(select(report_state.c.revision))
                        == revision + 1
                    )
                    manual = {
                        "annual_basic_pay": "500000",
                        "currency_code": "INR",
                        "effective_date": date.today().isoformat(),
                        "components": [
                            {
                                "code": "target_bonus",
                                "label": "Target bonus",
                                "method": "fixed",
                                "value": "10000",
                                "commitment": "target",
                            }
                        ],
                        "expected_version": 1,
                    }
                    changed = await client.put(base, headers=headers, json=manual)
                    assert changed.status_code == 200, changed.text
                    assert changed.json()["guaranteed_cost"] == "500000.00"
                    assert changed.json()["target_cost"] == "510000.00"
                    assert changed.json()["rule_version_id"] is None
                    await check_equity(client, headers, employee_id)
            finally:
                await transaction.rollback()
            assert (
                await connection.scalar(select(func.count()).select_from(employees))
                == before
            )
            assert not await connection.scalar(
                select(func.count())
                .select_from(compensation_rules)
                .where(compensation_rules.c.created_by == user_id)
            )
            assert not await connection.scalar(
                select(func.count())
                .select_from(compensation_packages)
                .where(compensation_packages.c.employee_id == employee_id)
            )
    finally:
        await engine.dispose()


async def check_equity(client, headers, employee_id):
    path = f"/api/employees/{employee_id}/equity"
    year = date.today().year
    report_path = f"/api/analytics/compensation?country_code=IN&currency_code=INR&metric=ctc&year={year}"
    before = (await client.get(report_path)).json()
    [before_group] = before["currencies"][0]["rows"]
    assert (await client.get(path)).json()["ctc"] is None
    assert (
        await client.put(f"{path}/not-applicable", headers=headers)
    ).status_code == 204
    assert (await client.get(path)).json()["ctc"] == "500000.00"
    allocation = {"year": year, "currency_code": "INR", "amount": "20000"}
    today = date.today().isoformat()
    award = {
        "kind": "rsu",
        "units": "100",
        "grant_date": today,
        "grant_currency": "USD",
        "package_currency": "INR",
        "valuation": "8000",
        "valuation_date": today,
        "allocations": [allocation],
    }
    assert (await client.post(f"{path}/awards", json=award)).status_code == 403
    created = await client.post(f"{path}/awards", headers=headers, json=award)
    assert created.status_code == 201, created.text

    option = award | {"kind": "option", "exercise_price": "4.1250", "allocations": []}
    second = await client.post(f"{path}/awards", headers=headers, json=option)
    assert second.status_code == 201, second.text
    assert (await client.get(path)).json()["equity_cost"] is None
    second_path = f"{path}/awards/{second.json()['id']}"
    assert (
        await client.put(second_path, headers=headers, json=option)
    ).status_code == 409
    updated = await client.put(
        second_path,
        headers=headers,
        json=option
        | {
            "expected_version": 1,
            "allocations": [allocation | {"amount": "0"}],
        },
    )
    assert updated.status_code == 200, updated.text
    totals = (await client.get(path)).json()
    assert (totals["equity_cost"], totals["ctc"], totals["target_ctc"]) == (
        "20000.00",
        "520000.00",
        "530000.00",
    )
    assert totals["awards"][0]["unscheduled_units"] == "100"
    after = (await client.get(report_path)).json()
    [after_group] = after["currencies"][0]["rows"]
    assert after_group["headcount"] == before_group["headcount"] + 1
    [country] = after["composition"]
    [before_country] = before["composition"]
    assert Decimal(country["total"]) - Decimal(before_country["total"] or 0) == Decimal(
        "520000"
    )
    assert sum(Decimal(line["amount"]) for line in country["components"]) == Decimal(
        country["total"]
    )
    assert after["revision"] > before["revision"]


def test_configured_database_compensation_rollback(monkeypatch):
    if os.environ.get("RUN_CONFIGURED_DB_TESTS") != "1":
        pytest.skip(
            "Set RUN_CONFIGURED_DB_TESTS=1 to use .env with rolled-back fixtures."
        )
    asyncio.run(check_compensation(monkeypatch))
