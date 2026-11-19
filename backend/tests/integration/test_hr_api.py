import asyncio
import json
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

import httpx2
from argon2 import PasswordHasher
from sqlalchemy import func, select

from payscope.auth.router import SESSION_COOKIE
from payscope.main import app
from payscope.models import (
    auth_sessions,
    countries,
    currencies,
    departments,
    employee_salaries,
    employees,
    hr_users,
    job_titles,
    report_state,
)
from payscope.salaries import service as salary_service

AUTH = "/api/auth"
EMPLOYEES = "/api/employees"
USER_ID = UUID("4008449f-9df1-45ee-a994-9215ea98eac2")
CREDENTIALS = {"email": "hr@example.test", "password": "directory-test-password"}


def api_client():
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="https://testserver"
    )


async def add_test_data():
    async with app.state.engine.begin() as database:
        await database.execute(
            hr_users.insert().values(
                id=USER_ID,
                email=CREDENTIALS["email"],
                password_hash=PasswordHasher().hash(CREDENTIALS["password"]),
                display_name="HR Manager",
            )
        )
        await database.execute(
            countries.insert(),
            [
                {"code": "IN", "name": "India"},
                {"code": "US", "name": "United States"},
            ],
        )
        await database.execute(
            currencies.insert(),
            [
                {"code": "INR", "name": "Indian Rupee", "minor_units": 2},
                {"code": "USD", "name": "US Dollar", "minor_units": 2},
            ],
        )
        await database.execute(
            departments.insert(),
            [
                {"id": 1, "name": "Engineering"},
                {"id": 2, "name": "People"},
            ],
        )
        await database.execute(
            job_titles.insert(),
            [
                {"id": 1, "name": "Engineer"},
                {"id": 2, "name": "Recruiter"},
            ],
        )
        await database.execute(
            employees.insert(),
            [
                {
                    "id": number,
                    "employee_code": f"EMP-{number:06d}",
                    "full_name": name,
                    "country_code": country,
                    "department_id": department,
                    "job_title_id": title,
                }
                for number, name, country, department, title in [
                    (1, "Anita Rao", "IN", 1, 1),
                    (2, "Priya Rao", "IN", 1, 1),
                    (3, "Rao Chen", "US", 1, 1),
                    (4, "Chris Jones", "IN", 2, 2),
                ]
            ],
        )
        await database.execute(
            employee_salaries.insert().values(
                employee_id=1,
                annual_gross_base=Decimal("750000.00"),
                currency_code="INR",
                updated_by=USER_ID,
            )
        )


async def check_authentication():
    async with app.router.lifespan_context(app), api_client() as client:
        await add_test_data()
        for path in ("/api/reference-data", EMPLOYEES, f"{EMPLOYEES}/1/salary", f"{AUTH}/session"):
            response = await client.get(path)
            assert response.status_code == 401
            assert response.json()["detail"]["code"] == "SESSION_REQUIRED"

        for credentials in (
            CREDENTIALS | {"password": "wrong"},
            CREDENTIALS | {"email": "unknown@example.test"},
        ):
            response = await client.post(f"{AUTH}/sign-in", json=credentials)
            assert response.status_code == 401
            assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"

        simple_request = await client.post(
            f"{AUTH}/sign-in",
            content=json.dumps(CREDENTIALS),
            headers={"Content-Type": "text/plain"},
        )
        assert simple_request.status_code in (415, 422)
        assert "set-cookie" not in simple_request.headers

        login = await client.post(
            f"{AUTH}/sign-in", json=CREDENTIALS | {"email": "  HR@EXAMPLE.TEST  "}
        )
        assert login.status_code == 200, login.text
        assert login.headers["Cache-Control"] == "no-store"
        cookie = login.headers["set-cookie"].lower()
        assert all(flag in cookie for flag in ("httponly", "secure", "samesite=lax", "path=/api"))
        session_token = client.cookies[SESSION_COOKIE]
        csrf = login.json()["csrf_token"]
        assert login.json()["user"]["id"] == str(USER_ID)
        current = await client.get(f"{AUTH}/session")
        assert current.json() == login.json()
        assert current.headers["Cache-Control"] == "no-store"
        async with app.state.engine.connect() as database:
            hashes = (
                await database.execute(
                    select(auth_sessions.c.token_hash, auth_sessions.c.csrf_token_hash)
                )
            ).one()
        assert tuple(hashes) == (
            sha256(session_token.encode()).digest(),
            sha256(csrf.encode()).digest(),
        )

        denied = await client.post(f"{AUTH}/sign-out", headers={"X-CSRF-Token": "wrong"})
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "INVALID_CSRF_TOKEN"
        logout = await client.post(f"{AUTH}/sign-out", headers={"X-CSRF-Token": csrf})
        assert logout.status_code == 204
        assert "max-age=0" in logout.headers["set-cookie"].lower()
        revoked = await client.get(
            f"{AUTH}/session", headers={"Cookie": f"{SESSION_COOKIE}={session_token}"}
        )
        assert revoked.status_code == 401

        assert (await client.post(f"{AUTH}/sign-in", json=CREDENTIALS)).status_code == 200
        session_token = client.cookies[SESSION_COOKIE]
        async with app.state.engine.begin() as database:
            await database.execute(
                auth_sessions.update()
                .where(auth_sessions.c.token_hash == sha256(session_token.encode()).digest())
                .values(
                    created_at=func.now() - timedelta(hours=2),
                    expires_at=func.now() - timedelta(hours=1),
                )
            )
        assert (await client.get(EMPLOYEES)).status_code == 401

        assert (await client.post(f"{AUTH}/sign-in", json=CREDENTIALS)).status_code == 200
        async with app.state.engine.begin() as database:
            await database.execute(
                hr_users.update().where(hr_users.c.id == USER_ID).values(is_active=False)
            )
        assert (await client.get(EMPLOYEES)).status_code == 401
        assert (await client.post(f"{AUTH}/sign-in", json=CREDENTIALS)).status_code == 401


async def stored_salary_and_revision():
    async with app.state.engine.connect() as database:
        current = (
            await database.execute(
                select(
                    employee_salaries.c.annual_gross_base,
                    employee_salaries.c.currency_code,
                    employee_salaries.c.updated_by,
                ).where(employee_salaries.c.employee_id == 1)
            )
        ).one()
        revision = await database.scalar(select(report_state.c.revision))
    return (*current, revision)


async def check_directory_and_salary_updates(monkeypatch):
    first_salary = f"{EMPLOYEES}/1/salary"
    second_salary = f"{EMPLOYEES}/2/salary"
    async with app.router.lifespan_context(app), api_client() as client, api_client() as second:
        await add_test_data()
        denied = await client.put(
            first_salary, json={"annual_gross_base": "1", "currency_code": "USD"}
        )
        assert denied.status_code == 401

        login = await client.post(f"{AUTH}/sign-in", json=CREDENTIALS)
        second_login = await second.post(f"{AUTH}/sign-in", json=CREDENTIALS)
        assert login.status_code == second_login.status_code == 200
        csrf = {"X-CSRF-Token": login.json()["csrf_token"]}
        second_csrf = {"X-CSRF-Token": second_login.json()["csrf_token"]}

        options = (await client.get("/api/reference-data")).json()
        assert {country["code"] for country in options["countries"]} == {"IN", "US"}
        assert {currency["code"] for currency in options["currencies"]} == {"INR", "USD"}
        assert {item["name"] for item in options["departments"]} == {"Engineering", "People"}
        assert {item["name"] for item in options["job_titles"]} == {"Engineer", "Recruiter"}

        results = await client.get(EMPLOYEES, params={"search": "  rAo  "})
        assert results.status_code == 200, results.text
        assert results.json()["total"] == 3
        filters = {
            "search": "rao",
            "country_code": "in",
            "department_id": 1,
            "job_title_id": 1,
            "page_size": 1,
        }
        for page, ids in ((1, [1]), (2, [2]), (3, [])):
            result = (await client.get(EMPLOYEES, params=filters | {"page": page})).json()
            assert (result["page"], result["page_size"], result["total"]) == (page, 1, 2)
            assert [row["id"] for row in result["items"]] == ids
        far_page = await client.get(
            EMPLOYEES, params=filters | {"page": 2**31 - 1, "page_size": 100}
        )
        assert far_page.status_code == 200
        assert far_page.json()["items"] == []
        assert far_page.json()["total"] == 2
        code = (await client.get(EMPLOYEES, params={"search": "emp-000004"})).json()
        assert [row["employee_code"] for row in code["items"]] == ["EMP-000004"]
        assert (await client.get(EMPLOYEES, params={"search": "%"})).json()["total"] == 0
        assert (await client.get(EMPLOYEES, params={"page_size": 101})).status_code == 422

        details = (await client.get(f"{EMPLOYEES}/1")).json()
        assert details["salary"]["annual_gross_base"] == "750000.00"
        assert (await client.get(second_salary)).json() is None
        missing = await client.get(f"{EMPLOYEES}/999/salary")
        assert missing.status_code == 404
        assert missing.json()["detail"]["code"] == "EMPLOYEE_NOT_FOUND"

        new_salary = {"annual_gross_base": "0.01", "currency_code": "USD"}
        denied = await client.put(second_salary, json=new_salary)
        assert denied.status_code == 403
        wrong_session = await client.put(second_salary, headers=second_csrf, json=new_salary)
        assert wrong_session.status_code == 403
        invalid = await client.put(
            second_salary, headers=csrf, json=new_salary | {"annual_gross_base": "0.001"}
        )
        assert invalid.status_code == 422
        assert invalid.json()["detail"][0]["loc"] == ["body", "annual_gross_base"]
        assert "input" not in invalid.json()["detail"][0]
        assert (await stored_salary_and_revision())[-1] == 0

        created = await client.put(second_salary, headers=csrf, json=new_salary)
        assert created.status_code == 200, created.text
        assert (await client.get(second_salary)).json()["annual_gross_base"] == "0.01"
        assert (await stored_salary_and_revision())[-1] == 1

        existing = await stored_salary_and_revision()
        advance_revision = salary_service.advance_report_revision

        async def fail_after_revision(database):
            await advance_revision(database)
            raise RuntimeError("Simulated failure before commit")

        with monkeypatch.context() as patch:
            patch.setattr(salary_service, "advance_report_revision", fail_after_revision)
            failed = await client.put(first_salary, headers=csrf, json=new_salary)
            assert failed.status_code == 500
        assert await stored_salary_and_revision() == existing

        amounts = ("999999999.99", "84250.12")
        one, two = await asyncio.gather(
            client.put(
                first_salary, headers=csrf, json=new_salary | {"annual_gross_base": amounts[0]}
            ),
            second.put(
                first_salary,
                headers=second_csrf,
                json=new_salary | {"annual_gross_base": amounts[1]},
            ),
        )
        assert one.status_code == two.status_code == 200
        assert (one.json()["annual_gross_base"], two.json()["annual_gross_base"]) == amounts
        final_amount, currency, updated_by, revision = await stored_salary_and_revision()
        assert final_amount in {Decimal(amount) for amount in amounts}
        assert (currency, updated_by, revision) == ("USD", USER_ID, 3)


def test_hr_sign_in_csrf_and_session_revocation(migrated_database):
    asyncio.run(check_authentication())


def test_directory_and_atomic_salary_updates(migrated_database, monkeypatch):
    asyncio.run(check_directory_and_salary_updates(monkeypatch))
