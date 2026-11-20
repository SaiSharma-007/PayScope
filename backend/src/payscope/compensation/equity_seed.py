from datetime import date
from decimal import Decimal
from hashlib import sha256
from uuid import uuid5

from sqlalchemy import exists, select, text

from payscope.compensation.seed import NAMESPACE, PROFILES, demo_version_id
from payscope.database import advance_report_revision
from payscope.models import (
    compensation_packages as packages,
)
from payscope.models import (
    employee_salaries,
    employees,
    hr_users,
)
from payscope.models import (
    equity_allocations as allocations,
)
from payscope.models import (
    equity_awards as awards,
)
from payscope.models import (
    equity_elections as elections,
)


def demo_equity(record, today):
    code = record["employee_code"]
    bucket = int.from_bytes(sha256(code.encode()).digest()[:4]) % 100
    if bucket < 5:
        return None, []
    if bucket < 73:
        return "no_equity", []

    kinds = (
        ("rsu", "option") if bucket >= 94 else ("rsu",) if bucket < 86 else ("option",)
    )
    grant_date = max(record["effective_date"], date(today.year - 2 - bucket % 3, 1, 1))
    last_year = today.year + 1
    currency = record["currency_code"]
    result = []
    for kind in kinds:
        award_id = uuid5(NAMESPACE, f"demo-equity:{code}:{kind}")
        award = {
            "id": award_id,
            "employee_id": record["employee_id"],
            "kind": kind,
            "units": 100,
            "version": 1,
            "grant_date": grant_date,
            "grant_currency": currency,
            "exercise_price": 10 if kind == "option" else None,
            "last_year": last_year,
            "vesting": [],
            "updated_by": record["updated_by"],
        }
        rate = Decimal("0.04" if kind == "rsu" else "0.02")
        years = [
            {
                "award_id": award_id,
                "year": year,
                "currency_code": currency,
                "amount": Decimal("0.00")
                if (year + bucket) % 11 == 0
                else (
                    record["annual_basic_pay"] * rate * (year - grant_date.year + 3) / 4
                ).quantize(Decimal("0.01")),
            }
            for year in range(grant_date.year, last_year + 1)
            if not (year == today.year and bucket % 9 == 0)
        ]
        result.append((award, years))
    return "awards", result


async def seed_equity(engine, *, apply=False):
    today = date.today()
    demo_versions = [
        demo_version_id(country, with_target=with_target)
        for country in PROFILES
        for with_target in (False, True)
    ]
    demo_employees = (
        select(employees.c.id)
        .where(
            employees.c.employee_code.op("~")(r"^EMP-[0-9]{6}$"),
            employees.c.employee_code.between("EMP-000001", "EMP-010000"),
        )
        .order_by(employees.c.id)
    )
    async with engine.begin() as connection:
        if apply:
            await connection.execute(text("SELECT pg_advisory_xact_lock(714520019)"))
            await connection.execute(demo_employees.with_for_update())
        demo_hr = (
            select(hr_users.c.id)
            .where(hr_users.c.email == "hr@payscope.example")
            .scalar_subquery()
        )
        records = (
            await connection.execute(
                select(
                    employees.c.employee_code,
                    packages.c.employee_id,
                    packages.c.currency_code,
                    packages.c.annual_basic_pay,
                    packages.c.effective_date,
                    packages.c.updated_by,
                )
                .select_from(employees.join(packages).join(employee_salaries))
                .where(
                    employees.c.id.in_(demo_employees),
                    packages.c.rule_version_id.in_(demo_versions),
                    packages.c.version == 1,
                    packages.c.updated_by == demo_hr,
                    packages.c.effective_date <= today,
                    packages.c.guaranteed_cost == employee_salaries.c.annual_gross_base,
                    packages.c.currency_code == employee_salaries.c.currency_code,
                    ~exists().where(awards.c.employee_id == employees.c.id),
                    ~exists().where(elections.c.employee_id == employees.c.id),
                )
                .order_by(employees.c.id)
            )
        ).mappings()
        no_equity, award_rows, allocation_rows = [], [], []
        unconfigured = 0
        for record in records:
            status, entries = demo_equity(record, today)
            if status is None:
                unconfigured += 1
            elif status == "no_equity":
                no_equity.append(
                    {
                        "employee_id": record["employee_id"],
                        "updated_by": record["updated_by"],
                    }
                )
            for award, years in entries:
                award_rows.append(award)
                allocation_rows.extend(years)

        summary = {
            "no_equity": len(no_equity),
            "awards": len(award_rows),
            "allocations": len(allocation_rows),
            "unconfigured": unconfigured,
        }
        if apply and (no_equity or award_rows):
            for table, rows in (
                (elections, no_equity),
                (awards, award_rows),
                (allocations, allocation_rows),
            ):
                if rows:
                    await connection.execute(table.insert(), rows)
            await advance_report_revision(connection)
        return summary
