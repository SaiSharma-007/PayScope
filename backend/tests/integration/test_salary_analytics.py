import asyncio
import os
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx2
import pytest
from argon2 import PasswordHasher
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text

from payscope.analytics.cache import REPORT_CACHE_TTL, ReportCache
from payscope.analytics.schemas import ReportFilters
from payscope.main import app
from payscope.models import employee_salaries, hr_users

REPORT = "/api/analytics/salary-summary"
CREDENTIALS = {"email": "hr@example.test", "password": "analytics-test-password"}


def client():
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="https://testserver"
    )


async def seed_reports():
    user_id = uuid4()
    async with app.state.engine.begin() as database:
        await database.execute(
            hr_users.insert().values(
                id=user_id,
                email=CREDENTIALS["email"],
                password_hash=PasswordHasher().hash(CREDENTIALS["password"]),
                display_name="HR Manager",
            )
        )
        for statement in (
            "INSERT INTO app.countries VALUES ('IN','India'),('US','United States'),('DE','Germany')",
            "INSERT INTO app.currencies VALUES ('USD','US Dollar',2),('INR','Indian Rupee',2)",
            "INSERT INTO app.departments (id,name) VALUES (1,'Engineering'),(2,'Finance'),(3,'People')",
            "INSERT INTO app.job_titles (id,name) VALUES (1,'Engineer'),(2,'Analyst')",
            """INSERT INTO app.employees (id,employee_code,full_name,country_code,department_id,job_title_id)
            VALUES (1,'EMP-1','Anita Rao','IN',1,1),(2,'EMP-2','Meera Rao','IN',1,1),
                   (3,'EMP-3','Alex Chen','US',2,2),(4,'EMP-4','Maya Lewis','US',2,2),
                   (5,'EMP-5','Kavya Menon','IN',2,2),(6,'EMP-6','Kiran Das','IN',1,1),
                   (7,'EMP-7','Priya Singh','IN',1,1),(8,'EMP-8','Arjun Shah','IN',1,1),
                   (9,'EMP-9','Emil Fischer','DE',3,2)""",
        ):
            await database.execute(text(statement))
        await database.execute(
            employee_salaries.insert(),
            [
                {
                    "employee_id": employee_id,
                    "annual_gross_base": Decimal(amount),
                    "currency_code": currency,
                    "updated_by": user_id,
                }
                for employee_id, amount, currency in (
                    (1, "100.00", "USD"),
                    (2, "100.01", "USD"),
                    (3, "100.01", "USD"),
                    (4, "100.01", "USD"),
                    (5, "100.00", "USD"),
                    (6, "150.00", "INR"),
                    (7, "200.00", "INR"),
                    (8, "300.00", "INR"),
                )
            ],
        )


async def sign_in(api):
    result = await api.post("/api/auth/sign-in", json=CREDENTIALS)
    assert result.status_code == 200
    return {"X-CSRF-Token": result.json()["csrf_token"]}


async def check_calculations():
    async with app.router.lifespan_context(app), client() as api:
        await seed_reports()
        assert (await api.get(REPORT)).status_code == 401
        await sign_in(api)
        summary = await api.get(REPORT)
        assert summary.status_code == 200, summary.text
        assert summary.headers["X-Report-Cache"] == "bypass"
        body = summary.json()
        assert body["revision"] == 0 and body["group_by"] is None
        inr, usd = body["rows"]
        assert (inr["currency_code"], inr["headcount"], inr["median"], inr["mean"]) == (
            "INR",
            3,
            "200.00",
            "216.67",
        )
        assert (usd["currency_code"], usd["headcount"], usd["median"], usd["mean"]) == (
            "USD",
            5,
            "100.01",
            "100.01",
        )
        assert (usd["minimum"], usd["maximum"]) == ("100.00", "100.01")

        grouped = (await api.get(REPORT, params={"group_by": "department"})).json()["rows"]
        usd_groups = [row for row in grouped if row["currency_code"] == "USD"]
        assert [(row["group_id"], row["mean"], row["median"]) for row in usd_groups] == [
            (2, "100.01", "100.01"),
            (1, "100.01", "100.01"),
        ]
        assert [row["group_name"] for row in usd_groups] == ["Finance", "Engineering"]
        countries = (await api.get(REPORT, params={"group_by": "country"})).json()["rows"]
        assert {row["group_id"] for row in countries} == {"IN", "US"}
        filtered = await api.get(
            REPORT,
            params={
                "country_code": "in",
                "department_id": 1,
                "job_title_id": 1,
                "group_by": "job_title",
            },
        )
        assert [(row["group_name"], row["headcount"]) for row in filtered.json()["rows"]] == [
            ("Engineer", 3),
            ("Engineer", 2),
        ]
        assert (await api.get(REPORT, params={"country_code": "DE"})).json()["rows"] == []
        assert (await api.get(REPORT, params={"group_by": "currency"})).status_code == 422


async def check_cache(monkeypatch):
    filters = ReportFilters(country_code="IN", group_by="department")
    async with app.router.lifespan_context(app), client() as api:
        await seed_reports()
        cache = app.state.report_cache
        cache.prefix += f":test:{uuid4().hex}"
        csrf = await sign_in(api)
        directory = (await api.get("/api/employees", params={"search": "EMP-1"})).json()
        employee_id = directory["items"][0]["id"]
        params = filters.model_dump(exclude_none=True)
        first = await api.get(REPORT, params=params)
        assert first.status_code == 200
        assert first.headers["X-Report-Cache"] == "miss"
        old_key = cache.key(filters, 0)
        assert 0 < await cache.redis.ttl(old_key) <= REPORT_CACHE_TTL
        raw = await cache.get(filters, 0)
        assert [row.mean for row in raw.rows if row.headcount == 2] == [Decimal("100.005")]
        second = await api.get(REPORT, params=params | {"country_code": "in"})
        assert second.headers["X-Report-Cache"] == "hit"
        assert second.json() == first.json()

        async def update_salary(amount):
            response = await api.put(
                f"/api/employees/{employee_id}/salary",
                headers=csrf,
                json={"annual_gross_base": amount, "currency_code": "USD"},
            )
            assert response.status_code == 200, response.text

        await update_salary("200.00")
        fresh = await api.get(REPORT, params=params)
        assert fresh.headers["X-Report-Cache"] == "miss" and fresh.json()["revision"] == 1
        assert first.json()["rows"] != fresh.json()["rows"]
        assert await cache.redis.exists(old_key)

        async def edit_between_cache_lookup_and_aggregation(_cache, _filters, revision):
            assert revision == 1
            await update_salary("300.00")
            return None

        during_edit = params | {"group_by": "job_title"}
        with monkeypatch.context() as patch:
            patch.setattr(ReportCache, "get", edit_between_cache_lookup_and_aggregation)
            updated = await api.get(REPORT, params=during_edit)
        assert updated.json()["revision"] == 2
        assert any(row["maximum"] == "300.00" for row in updated.json()["rows"])
        assert (await api.get(REPORT, params=during_edit)).headers["X-Report-Cache"] == "hit"
        assert not await cache.redis.exists(cache.key(ReportFilters(**during_edit), 1))

        with monkeypatch.context() as patch:
            patch.setattr(ReportCache, "get", AsyncMock(side_effect=TimeoutError))
            bypass = await api.get(REPORT, params=during_edit)
        assert bypass.headers["X-Report-Cache"] == "bypass"
        assert bypass.json() == updated.json()

        with monkeypatch.context() as patch:
            patch.setattr(ReportCache, "put", AsyncMock(side_effect=RedisConnectionError))
            failed_write = await api.get(REPORT, params={"group_by": "country"})
        assert failed_write.status_code == 200
        assert failed_write.json()["revision"] == 2


def test_salary_report_calculations(migrated_database):
    asyncio.run(check_calculations())


def test_report_cache_revision_and_fallback(migrated_database, monkeypatch):
    redis_url = os.environ.get("TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("TEST_REDIS_URL is unset")
    monkeypatch.setenv("REDIS_URL", redis_url)
    asyncio.run(check_cache(monkeypatch))
