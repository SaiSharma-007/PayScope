"""Fictional country packages that preserve each seeded employee's recorded total."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid5

from sqlalchemy import select, text

from payscope.compensation.calculator import calculate
from payscope.compensation.schemas import Component, PackageDraft, RuleDraft
from payscope.database import advance_report_revision
from payscope.models import (
    compensation_package_components as lines,
)
from payscope.models import (
    compensation_packages as packages,
)
from payscope.models import (
    compensation_rule_components as definitions,
)
from payscope.models import (
    compensation_rule_versions as versions,
)
from payscope.models import (
    compensation_rules as rules,
)
from payscope.models import (
    employee_salaries,
    employees,
    hr_users,
)
from payscope.seed_data import LOCATIONS

NAMESPACE = UUID("b5b4f9c1-d38f-454e-953b-98015d6d49e4")
PROFILES = {
    "IN": (
        "0.60",
        "Housing allowance (demo)",
        "30",
        "Employer retirement (demo)",
        "10",
        "6",
    ),
    "US": (
        "0.75",
        "Health benefit (demo)",
        "10",
        "Employer retirement (demo)",
        "5",
        "4",
    ),
    "GB": (
        "0.70",
        "Wellbeing allowance (demo)",
        "6",
        "Employer pension (demo)",
        "8",
        "4",
    ),
    "DE": (
        "0.65",
        "Mobility allowance (demo)",
        "5",
        "Employer social benefits (demo)",
        "25",
        "8",
    ),
    "FR": (
        "0.65",
        "Meal allowance (demo)",
        "4",
        "Employer social benefits (demo)",
        "30",
        "8",
    ),
}


def demo_rule(country: str) -> RuleDraft:
    _, allowance, allowance_rate, employer, employer_rate, deduction_rate = PROFILES[
        country
    ]
    return RuleDraft(
        name=f"{LOCATIONS[country].country} · Demo compensation",
        country_code=country,
        currency_code=LOCATIONS[country].currency,
        components=[
            Component(
                code="country_allowance",
                label=allowance,
                method="percent_of_base",
                value=allowance_rate,
            ),
            Component(
                code="employer_benefit",
                label=employer,
                category="employer_cost",
                method="percent_of_base",
                value=employer_rate,
            ),
            Component(
                code="custom_yearly_bonus",
                label="Custom yearly bonus (demo)",
                method="percent_of_base",
                value="1",
            ),
            Component(
                code="employee_contribution",
                label="Employee contribution (demo)",
                category="deduction",
                method="percent_of_base",
                value=deduction_rate,
                included_in_cost=False,
            ),
            Component(
                code="flexible_allowance", label="Flexible annual allowance", value="0"
            ),
        ],
    )


def demo_package(country: str, total: Decimal, effective_date: date):
    rule = demo_rule(country)
    basic = max(
        Decimal("0.01"),
        (total * Decimal(PROFILES[country][0])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
    )
    draft = PackageDraft(
        annual_basic_pay=format(basic, ".2f"),
        currency_code=rule.currency_code,
        effective_date=effective_date,
    )
    calculated = calculate(draft, rule.components)
    remainder = total - calculated.guaranteed_cost
    if remainder < 0:
        raise ValueError("The original total is too small for this demo profile.")
    draft = PackageDraft.model_validate(
        draft.model_dump(mode="json")
        | {
            "overrides": [
                dict(
                    code="flexible_allowance",
                    amount=format(remainder, ".2f"),
                    reason="Fictional allocation preserving the original recorded annual total.",
                )
            ]
        }
    )
    result = calculate(draft, rule.components)
    assert result.guaranteed_cost == result.target_cost == total
    return result


async def seed_compensation(engine, *, apply=False):
    async with engine.begin() as connection:
        if apply:
            await connection.execute(text("SELECT pg_advisory_xact_lock(714520019)"))
        query = (
            select(
                employees.c.id,
                employees.c.country_code,
                employee_salaries.c.annual_gross_base,
                employee_salaries.c.currency_code,
            )
            .select_from(employees.join(employee_salaries).outerjoin(packages))
            .where(
                employees.c.employee_code.op("~")(r"^EMP-[0-9]{6}$"),
                employees.c.employee_code.between("EMP-000001", "EMP-010000"),
                packages.c.employee_id.is_(None),
            )
            .order_by(employees.c.id)
        )
        if apply:
            query = query.with_for_update(of=employees)
        records = (await connection.execute(query)).mappings().all()
        summary = {}
        for record in records:
            country = record["country_code"]
            if (
                country not in PROFILES
                or record["currency_code"] != LOCATIONS[country].currency
            ):
                raise ValueError(
                    "A seeded employee has an unsupported country/currency. No compensation was changed."
                )
            item = summary.setdefault(
                country,
                {
                    "employees": 0,
                    "original_total": Decimal("0"),
                    "package_total": Decimal("0"),
                },
            )
            calculation = demo_package(
                country, record["annual_gross_base"], date(2026, 1, 1)
            )
            item["employees"] += 1
            item["original_total"] += record["annual_gross_base"]
            item["package_total"] += calculation.guaranteed_cost
        if not apply or not records:
            return {"created": 0, "eligible": len(records), "countries": summary}
        user_id = await connection.scalar(
            select(hr_users.c.id).where(hr_users.c.email == "hr@payscope.example")
        )
        if user_id is None:
            raise ValueError("Run the base seed before reframing compensation.")
        version_ids = {}
        for country in summary:
            draft = demo_rule(country)
            rule_id = uuid5(NAMESPACE, f"rule:{country}")
            version_id = uuid5(NAMESPACE, f"version:{country}:1")
            existing = (
                (
                    await connection.execute(
                        select(rules).where(rules.c.id == rule_id).with_for_update()
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing:
                from payscope.compensation.service import get_version

                saved = await get_version(connection, version_id)
                if not existing["active"] or saved.components != draft.components:
                    raise ValueError(
                        "A demo rule was changed or deactivated. Review it before enriching more employees."
                    )
            else:
                await connection.execute(
                    rules.insert().values(
                        id=rule_id,
                        name=draft.name,
                        country_code=country,
                        currency_code=draft.currency_code,
                        latest_version=1,
                        created_by=user_id,
                    )
                )
                await connection.execute(
                    versions.insert().values(
                        id=version_id,
                        rule_id=rule_id,
                        number=1,
                        name=draft.name,
                        created_by=user_id,
                    )
                )
                await connection.execute(
                    definitions.insert(),
                    [
                        dict(
                            version_id=version_id,
                            position=index,
                            **component.model_dump(),
                        )
                        for index, component in enumerate(draft.components)
                    ],
                )
            version_ids[country] = version_id
        for start in range(0, len(records), 250):
            package_rows, component_rows = [], []
            for record in records[start : start + 250]:
                calculation = demo_package(
                    record["country_code"],
                    record["annual_gross_base"],
                    date(2026, 1, 1),
                )
                package_rows.append(
                    dict(
                        employee_id=record["id"],
                        version=1,
                        effective_date=date(2026, 1, 1),
                        rule_version_id=version_ids[record["country_code"]],
                        updated_by=user_id,
                        **calculation.model_dump(
                            exclude={"components", "equity_status"}
                        ),
                    )
                )
                component_rows.extend(
                    dict(
                        employee_id=record["id"],
                        position=index,
                        **component.model_dump(exclude={"explanation"}),
                    )
                    for index, component in enumerate(calculation.components)
                )
            await connection.execute(packages.insert(), package_rows)
            await connection.execute(lines.insert(), component_rows)
        await advance_report_revision(connection)
        return {"created": len(records), "eligible": len(records), "countries": summary}
