import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

from argon2 import PasswordHasher
from redis.exceptions import ConnectionError
from sqlalchemy import text
from test_salary_analytics import CREDENTIALS, client, sign_in

from payscope.analytics.cache import ReportCache
from payscope.main import app
from payscope.models import hr_users

INSIGHTS = "/api/analytics/salary-insights"
YEAR = 2025


async def seed_workforce():
    async with app.state.engine.begin() as database:
        user_id = uuid4()
        await database.execute(
            hr_users.insert().values(
                id=user_id,
                email=CREDENTIALS["email"],
                display_name="HR Manager",
                password_hash=PasswordHasher().hash(CREDENTIALS["password"]),
            )
        )
        for statement in (
            "INSERT INTO app.countries VALUES ('IN','India'),('US','United States'),('DE','Germany')",
            "INSERT INTO app.currencies VALUES ('USD','US Dollar',2),('INR','Indian Rupee',2)",
            "INSERT INTO app.departments (id,name) VALUES (1,'Engineering'),(2,'People'),(3,'Finance')",
            "INSERT INTO app.job_titles (id,name) VALUES (1,'Engineer'),(2,'Analyst')",
            """INSERT INTO app.employees (id,employee_code,full_name,country_code,department_id,job_title_id)
                VALUES (1,'E1','Employee 1','IN',1,1),(2,'E2','Employee 2','IN',1,1),
                       (3,'E3','Employee 3','IN',1,1),(4,'E4','Employee 4','US',2,2),
                       (5,'E5','Employee 5','IN',3,2),(6,'E6','Employee 6','DE',3,2),
                       (7,'E7','Employee 7','IN',2,2)""",
        ):
            await database.execute(text(statement))
        await database.execute(
            text("""
            INSERT INTO app.employee_salaries (employee_id, annual_gross_base, currency_code, updated_by)
            VALUES (5, 250, 'INR', :user_id)
        """),
            {"user_id": user_id},
        )


async def save_package(
    api, headers, employee, base, currency, version=0, extra_components=()
):
    response = await api.put(
        f"/api/employees/{employee}/compensation",
        headers=headers,
        json={
            "annual_basic_pay": base,
            "currency_code": currency,
            "effective_date": f"{YEAR}-01-01",
            "expected_version": version,
            "components": [
                {"code": code, "label": code, "method": "fixed", "value": value}
                | attributes
                for code, value, attributes in (
                    ("allowance", "10", {}),
                    ("insurance", "5", {"category": "employer_cost"}),
                    ("bonus", "20", {"commitment": "target"}),
                    ("tax", "8", {"category": "deduction", "included_in_cost": False}),
                    ("excluded", "30", {"included_in_cost": False}),
                )
            ]
            + list(extra_components),
        },
    )
    assert response.status_code == 200, response.text


def award(kind, amount=None, *, last_year=YEAR, future_amount=None):
    allocations = (
        [{"year": YEAR, "amount": amount, "currency_code": "INR"}]
        if amount is not None
        else []
    )
    if future_amount is not None:
        allocations.append(
            {"year": YEAR + 1, "amount": future_amount, "currency_code": "INR"}
        )
    result = {
        "kind": kind,
        "units": "10",
        "grant_date": f"{YEAR}-01-01",
        "last_year": last_year,
        "grant_currency": "USD",
        "package_currency": "INR",
        "allocations": allocations,
    }
    if kind == "option":
        result["exercise_price"] = "1"
    return result


async def save_award(api, headers, employee, data):
    response = await api.post(
        f"/api/employees/{employee}/equity/awards",
        headers=headers,
        json=data,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def fetch(api, insight, **filters):
    response = await api.get(
        INSIGHTS, params={"insight": insight, "year": YEAR} | filters
    )
    assert response.status_code == 200, response.text
    return response.json(), response.headers["X-Report-Cache"]


async def check_insights(monkeypatch):
    async with app.router.lifespan_context(app), client() as api:
        await seed_workforce()
        assert (
            await api.get(INSIGHTS, params={"insight": "pay_distribution"})
        ).status_code == 401
        headers = await sign_in(api)
        for params in (
            {},
            {"insight": "unknown"},
            {"insight": "role_bands", "group_by": "department"},
            {"insight": "pay_distribution", "limit": 26},
            {"insight": "pay_distribution", "metric": "equity"},
            {"insight": "pay_distribution", "department_id": 0},
            {"insight": "equity_timeline", "year": YEAR, "start_year": YEAR - 20},
            {"insight": "equity_timeline", "currency_code": "CAD"},
        ):
            assert (await api.get(INSIGHTS, params=params)).status_code == 422, params

        entries = {}
        redis = AsyncMock()
        redis.get.side_effect = entries.get
        redis.set.side_effect = lambda key, value, **_: entries.update({key: value})
        monkeypatch.setattr(app.state, "report_cache", ReportCache(redis, "test"))
        before, status = await fetch(api, "pay_distribution", country_code="IN")
        assert status == "miss"
        assert (await fetch(api, "pay_distribution", country_code="in")) == (
            before,
            "hit",
        )

        for employee, base, currency in (
            (1, "100.01", "INR"),
            (2, "200", "INR"),
            (3, "300", "INR"),
            (4, "1000", "USD"),
            (7, "50", "INR"),
        ):
            await save_package(api, headers, employee, base, currency)

        after, status = await fetch(api, "pay_distribution", country_code="IN")
        assert status == "miss" and after["revision"] == before["revision"] + 5
        [india] = after["currencies"][0]["rows"]
        assert india["percentiles"] == {
            "p10": "65.00",
            "p25": "87.51",
            "p50": "150.01",
            "p75": "225.00",
            "p90": "270.00",
        }
        assert (
            india["population"],
            india["eligible"],
            india["missing"],
            india["spread"],
        ) == (5, 4, 1, "250.00")
        overview, _ = await fetch(api, "country_comparison")
        assert overview["employees"] == 7 and overview["without_currency"] == 1
        assert overview["currencies"][0]["rows"] == [india]
        [us] = overview["currencies"][1]["rows"]
        assert us["group_id"] == "US" and set(us["percentiles"].values()) == {"1000.00"}
        missing, _ = await fetch(api, "pay_distribution", department_id=3)
        [incomplete] = missing["currencies"][0]["rows"]
        assert incomplete["eligible"] == 0 and set(
            incomplete["percentiles"].values()
        ) == {None}
        assert (await fetch(api, "role_bands", department_id=999))[0][
            "currencies"
        ] == []

        for employee in (3, 4, 7):
            assert (
                await api.put(
                    f"/api/employees/{employee}/equity/not-applicable",
                    headers=headers,
                )
            ).status_code == 204
        await save_award(
            api, headers, 1, award("rsu", "25", last_year=YEAR + 1, future_amount="50")
        )
        option_id = await save_award(api, headers, 1, award("option"))
        await save_award(api, headers, 2, award("rsu", "10"))
        await save_award(api, headers, 2, award("option"))
        before, _ = await fetch(api, "guaranteed_vs_target_ctc", country_code="IN")
        assert before["currencies"][0]["eligible"] == 2
        timeline, _ = await fetch(
            api, "equity_timeline", department_id=1, start_year=YEAR
        )
        options, rsus = timeline["currencies"][0]["rows"]
        assert (options["amount"], options["missing"], options["recorded_zero"]) == (
            None,
            2,
            0,
        )
        assert (rsus["amount"], rsus["eligible"], rsus["population"]) == ("35.00", 2, 2)

        response = await api.put(
            f"/api/employees/1/equity/awards/{option_id}",
            headers=headers,
            json=award("option", "0") | {"expected_version": 1},
        )
        assert response.status_code == 200, response.text
        paired, status = await fetch(api, "guaranteed_vs_target_ctc", country_code="IN")
        assert status == "miss" and paired["revision"] == before["revision"] + 1
        [india] = paired["currencies"][0]["rows"]
        assert (india["eligible"], india["missing"]) == (3, 2)
        assert (india["guaranteed_ctc"], india["target_ctc"]) == ("520.01", "580.01")
        bands, _ = await fetch(api, "role_bands", country_code="IN", metric="ctc")
        engineer, analyst = sorted(
            bands["currencies"][0]["rows"], key=lambda row: row["group_id"]
        )
        assert (
            engineer["group_id"],
            engineer["eligible"],
            engineer["percentiles"]["p50"],
        ) == ("1", 2, "227.51")
        assert analyst["eligible"] == 1

        mixed, _ = await fetch(
            api, "compensation_mix", country_code="IN", metric="target_ctc"
        )
        [mix] = mixed["currencies"][0]["rows"]
        assert (
            mix["eligible"] == india["eligible"]
            and mix["amount"] == india["target_ctc"]
        )
        totals = {line["code"]: Decimal(line["amount"]) for line in mix["components"]}
        assert totals == {
            "allowance": 30,
            "basic_pay": Decimal("450.01"),
            "bonus": 60,
            "insurance": 15,
            "annual_equity": 25,
        }
        assert sum(totals.values()) == sum(
            Decimal(line["amount"]) for line in mix["categories"]
        )

        shares, _ = await fetch(
            api,
            "headcount_vs_payroll",
            country_code="IN",
            group_by="department",
            limit=1,
        )
        [currency] = shares["currencies"]
        [team] = currency["rows"]
        assert (
            currency["group_count"],
            currency["population"],
            currency["eligible"],
        ) == (3, 5, 4)
        assert currency["payroll_total"] == "710.01"
        assert (team["group_id"], team["headcount_share"], team["payroll_share"]) == (
            "1",
            "60.00",
            "90.85",
        )
        drill_down, _ = await fetch(
            api,
            "payroll_concentration",
            country_code="IN",
            department_id=1,
            group_by="job_title",
        )
        [role] = drill_down["currencies"][0]["rows"]
        assert (role["group_id"], role["amount"], role["payroll_share"]) == (
            "1",
            "645.01",
            "100.00",
        )

        timeline, status = await fetch(
            api,
            "equity_timeline",
            country_code="IN",
            department_id=1,
            year=YEAR + 1,
            start_year=YEAR,
        )
        options, rsus, future = timeline["currencies"][0]["rows"]
        assert status == "miss"
        assert (options["amount"], options["missing"], options["recorded_zero"]) == (
            "0.00",
            1,
            1,
        )
        assert rsus["amount"] == "35.00"
        assert (future["year"], future["kind"], future["amount"]) == (
            YEAR + 1,
            "rsu",
            "50.00",
        )

        legacy = await api.get(
            "/api/analytics/compensation",
            params={
                "country_code": "IN",
                "metric": "ctc",
                "year": YEAR,
            },
        )
        assert legacy.status_code == 200, legacy.text
        assert legacy.json()["composition"][0]["total"] == india["guaranteed_ctc"]

        extras = [
            {
                "code": f"extra_{i}",
                "label": f"Extra {i}",
                "method": "fixed",
                "value": "1",
            }
            for i in range(18)
        ]
        await save_package(
            api, headers, 7, "50", "INR", version=1, extra_components=extras
        )
        capped, _ = await fetch(
            api, "compensation_mix", country_code="IN", department_id=2
        )
        [mix] = capped["currencies"][0]["rows"]
        [other] = [line for line in mix["components"] if line["code"] is None]
        assert (len(mix["components"]), other["component_count"], other["amount"]) == (
            17,
            5,
            "5.00",
        )
        assert (
            sum(Decimal(line["amount"]) for line in mix["components"])
            == Decimal(mix["amount"])
            == 83
        )

        redis.get.side_effect = ConnectionError("Unavailable")
        assert await fetch(
            api, "compensation_mix", country_code="IN", department_id=2
        ) == (capped, "miss")


def test_salary_insights(migrated_database, monkeypatch):
    asyncio.run(check_insights(monkeypatch))
