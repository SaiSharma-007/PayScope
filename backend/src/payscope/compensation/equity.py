from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import delete, exists, func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from payscope.compensation.equity_schemas import AwardDraft
from payscope.compensation.schemas import decimal_text
from payscope.compensation.service import failure, field_error
from payscope.database import advance_report_revision
from payscope.employees.service import missing_employee
from payscope.models import (
    compensation_packages,
    currencies,
    employees,
    equity_allocations,
    equity_awards,
    equity_elections,
)

EQUITY_BY_EMPLOYEE = """
    SELECT a.employee_id,
           count(*) FILTER (WHERE a.grant_date < :period_end AND (a.last_year IS NULL OR a.last_year >= :year)) AS relevant,
           count(l.amount) FILTER (WHERE a.grant_date < :period_end AND (a.last_year IS NULL OR a.last_year >= :year)) AS allocated,
           coalesce(sum(l.amount) FILTER (WHERE a.grant_date < :period_end AND (a.last_year IS NULL OR a.last_year >= :year)), 0) AS cost
    FROM app.equity_awards a
    JOIN app.compensation_packages p ON p.employee_id = a.employee_id
    LEFT JOIN app.equity_allocations l ON l.award_id = a.id AND l.year = :year AND l.currency_code = p.currency_code
    GROUP BY a.employee_id
"""

EQUITY_COST = """CASE
    WHEN p.employee_id IS NULL THEN NULL
    WHEN n.employee_id IS NOT NULL THEN 0::numeric
    WHEN q.relevant = q.allocated THEN q.cost
END"""


async def lock_package(database, employee_id):
    found = await database.scalar(
        select(employees.c.id).where(employees.c.id == employee_id).with_for_update()
    )
    if found is None:
        raise missing_employee()
    currency = await database.scalar(
        select(compensation_packages.c.currency_code).where(
            compensation_packages.c.employee_id == employee_id
        )
    )
    if currency is None:
        raise failure(
            409,
            "PACKAGE_REQUIRED",
            "Save a compensation package before recording equity.",
        )
    return currency


async def equity_details(database, employee_id: int, year: int):
    row = (
        (
            await database.execute(
                text(f"""
        WITH equity AS ({EQUITY_BY_EMPLOYEE}), costs AS (
            SELECT p.currency_code, p.guaranteed_cost, p.target_cost, p.effective_date,
                   n.employee_id IS NOT NULL AS no_equity, {EQUITY_COST} AS equity_cost
            FROM app.compensation_packages p
            LEFT JOIN equity q ON q.employee_id = p.employee_id
            LEFT JOIN app.equity_elections n ON n.employee_id = p.employee_id
            WHERE p.employee_id = :employee_id
        )
        SELECT *, CASE WHEN effective_date < :period_end THEN (guaranteed_cost + equity_cost)::text END AS ctc,
               CASE WHEN effective_date < :period_end THEN (target_cost + equity_cost)::text END AS target_ctc
        FROM costs
    """),
                {
                    "employee_id": employee_id,
                    "year": year,
                    "period_end": date(year + 1, 1, 1),
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        if not await database.scalar(
            select(exists().where(employees.c.id == employee_id))
        ):
            raise missing_employee()
        return None

    awards = (
        (
            await database.execute(
                select(equity_awards)
                .where(equity_awards.c.employee_id == employee_id)
                .order_by(equity_awards.c.grant_date, equity_awards.c.id)
            )
        )
        .mappings()
        .all()
    )
    allocations = {}
    if awards:
        result = await database.execute(
            select(equity_allocations)
            .join(equity_awards)
            .where(equity_awards.c.employee_id == employee_id)
            .order_by(equity_allocations.c.year)
        )
        for line in result.mappings():
            allocations.setdefault(line["award_id"], []).append(
                {
                    "year": line["year"],
                    "amount": format(line["amount"], ".2f"),
                    "currency_code": line["currency_code"],
                }
            )
    data = []
    for award in awards:
        item = dict(award)
        for field in ("units", "exercise_price", "valuation"):
            item[field] = None if item[field] is None else decimal_text(item[field])
        item["allocations"] = allocations.get(item["id"], [])
        item["unscheduled_units"] = decimal_text(
            award["units"] - sum(Decimal(entry["units"]) for entry in award["vesting"])
        )
        data.append(item)
    return dict(row) | {
        "year": year,
        "awards": data,
        "equity_cost": None
        if row["equity_cost"] is None
        else format(row["equity_cost"], ".2f"),
        "guaranteed_cost": format(row["guaranteed_cost"], ".2f"),
        "target_cost": format(row["target_cost"], ".2f"),
        "status": "not_applicable"
        if row["no_equity"]
        else "complete"
        if row["equity_cost"] is not None
        else "incomplete",
    }


async def save_award(
    database,
    employee_id: int,
    draft: AwardDraft,
    user_id: UUID,
    award_id: UUID | None = None,
):
    currency = await lock_package(database, employee_id)
    if currency != draft.package_currency:
        raise failure(
            409,
            "PACKAGE_CURRENCY_CHANGED",
            "The package currency changed. Reload this employee before saving.",
        )
    if not await database.scalar(
        select(exists().where(currencies.c.code == draft.grant_currency))
    ):
        raise field_error("grant_currency", "Grant currency is unavailable.")
    existing = {}
    if award_id is not None:
        version = await database.scalar(
            select(equity_awards.c.version).where(
                equity_awards.c.id == award_id,
                equity_awards.c.employee_id == employee_id,
            )
        )
        if version is None:
            raise failure(404, "AWARD_NOT_FOUND", "Equity award not found.")
        if version != draft.expected_version:
            raise failure(
                409,
                "AWARD_CHANGED",
                "This award changed while you were editing. Reload before saving.",
            )
        rows = await database.execute(
            select(equity_allocations).where(equity_allocations.c.award_id == award_id)
        )
        existing = {row.year: (row.currency_code, row.amount) for row in rows}
    elif draft.expected_version != 0:
        raise field_error("expected_version", "New awards start at version zero.")
    for index, allocation in enumerate(draft.allocations):
        if allocation.currency_code != currency and existing.get(allocation.year) != (
            allocation.currency_code,
            allocation.amount,
        ):
            raise field_error(
                ("allocations", index, "currency_code"),
                "Enter new or changed allocations in the current package currency.",
            )

    values = draft.model_dump(
        exclude={"package_currency", "allocations", "vesting", "expected_version"}
    )
    values |= {
        "updated_by": user_id,
        "version": draft.expected_version + 1,
        "updated_at": func.clock_timestamp(),
        "vesting": [
            row.model_dump(mode="json")
            for row in sorted(draft.vesting, key=lambda row: row.date)
        ],
    }
    if award_id is None:
        award_id = uuid4()
        await database.execute(
            equity_awards.insert().values(
                id=award_id, employee_id=employee_id, **values
            )
        )
    else:
        await database.execute(
            update(equity_awards).where(equity_awards.c.id == award_id).values(**values)
        )
        await database.execute(
            delete(equity_allocations).where(equity_allocations.c.award_id == award_id)
        )
    if draft.allocations:
        await database.execute(
            equity_allocations.insert(),
            [
                allocation.model_dump() | {"award_id": award_id}
                for allocation in draft.allocations
            ],
        )
    await database.execute(
        delete(equity_elections).where(equity_elections.c.employee_id == employee_id)
    )
    await advance_report_revision(database)
    await database.commit()
    return {"id": award_id, "version": values["version"]}


async def mark_no_equity(database, employee_id, user_id):
    await lock_package(database, employee_id)
    if await database.scalar(
        select(exists().where(equity_awards.c.employee_id == employee_id))
    ):
        raise failure(409, "AWARDS_EXIST", "This employee has recorded equity awards.")
    result = await database.execute(
        insert(equity_elections)
        .values(employee_id=employee_id, updated_by=user_id)
        .on_conflict_do_nothing()
        .returning(equity_elections.c.employee_id)
    )
    if result.scalar_one_or_none() is not None:
        await advance_report_revision(database)
    await database.commit()
