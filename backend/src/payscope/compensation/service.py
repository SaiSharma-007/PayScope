from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from payscope.compensation.calculator import calculate
from payscope.compensation.schemas import (
    CalculatedComponent,
    Component,
    PackageDraft,
    PackageResponse,
    PackageSave,
    RuleDraft,
    RulePublish,
    RuleStatus,
    RuleSummary,
    RuleVersion,
    decimal_text,
)
from payscope.database import advance_report_revision
from payscope.employees.service import missing_employee
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
    countries,
    currencies,
    employees,
)


def failure(status: int, code: str, message: str):
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def field_error(field: str | tuple[str | int, ...], message: str):
    location = (field,) if isinstance(field, str) else field
    return HTTPException(
        status_code=422,
        detail=[{"loc": ["body", *location], "msg": message, "type": "value_error"}],
    )


def component_from_row(row) -> Component:
    values = {name: row[name] for name in Component.model_fields}
    values["value"] = decimal_text(row["value"])
    return Component.model_validate(values)


async def validate_references(database: AsyncSession, draft: RuleDraft):
    country, currency = (
        await database.execute(
            select(
                exists().where(countries.c.code == draft.country_code),
                exists().where(currencies.c.code == draft.currency_code),
            )
        )
    ).one()
    if not country:
        raise field_error("country_code", "Country is unavailable.")
    if not currency:
        raise field_error("currency_code", "Currency is unavailable.")


def rule_query():
    return select(rules, versions.c.id.label("version_id")).join(
        versions,
        (versions.c.rule_id == rules.c.id)
        & (versions.c.number == rules.c.latest_version),
    )


async def list_rules(
    database: AsyncSession, country_code=None, currency_code=None, active=None, page=1
):
    conditions = []
    for column, value in (
        (rules.c.country_code, country_code),
        (rules.c.currency_code, currency_code),
        (rules.c.active, active),
    ):
        if value is not None:
            conditions.append(column == value)
    rows = (
        (
            await database.execute(
                rule_query()
                .where(*conditions)
                .order_by(rules.c.name, rules.c.id)
                .limit(50)
                .offset((page - 1) * 50)
            )
        )
        .mappings()
        .all()
    )
    total = await database.scalar(
        select(func.count()).select_from(rules).where(*conditions)
    )
    return {
        "items": [RuleSummary.model_validate(row) for row in rows],
        "total": total,
        "page": page,
    }


async def get_rule(database: AsyncSession, rule_id: UUID):
    row = (
        (await database.execute(rule_query().where(rules.c.id == rule_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise failure(404, "RULE_NOT_FOUND", "Compensation rule not found.")
    history = (
        (
            await database.execute(
                select(
                    versions.c.id,
                    versions.c.number,
                    versions.c.name,
                    versions.c.created_at,
                )
                .where(versions.c.rule_id == rule_id)
                .order_by(versions.c.number.desc())
            )
        )
        .mappings()
        .all()
    )
    return {
        "rule": RuleSummary.model_validate(row),
        "versions": [dict(item) for item in history],
    }


async def get_version(database: AsyncSession, version_id: UUID) -> RuleVersion:
    row = (
        (
            await database.execute(
                select(versions, rules.c.country_code, rules.c.currency_code)
                .join(rules)
                .where(versions.c.id == version_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise failure(404, "RULE_VERSION_NOT_FOUND", "Rule version not found.")
    components = (
        (
            await database.execute(
                select(definitions)
                .where(definitions.c.version_id == version_id)
                .order_by(definitions.c.position)
            )
        )
        .mappings()
        .all()
    )
    return RuleVersion(
        **row, components=[component_from_row(component) for component in components]
    )


async def add_version(
    database: AsyncSession, rule_id: UUID, number: int, draft: RuleDraft, user_id: UUID
):
    version_id = uuid4()
    await database.execute(
        versions.insert().values(
            id=version_id,
            rule_id=rule_id,
            number=number,
            name=draft.name,
            created_by=user_id,
        )
    )
    if draft.components:
        await database.execute(
            definitions.insert(),
            [
                dict(version_id=version_id, position=position, **component.model_dump())
                for position, component in enumerate(draft.components)
            ],
        )
    return version_id


async def create_rule(database: AsyncSession, draft: RuleDraft, user_id: UUID):
    await validate_references(database, draft)
    rule_id = uuid4()
    await database.execute(
        rules.insert().values(
            id=rule_id,
            name=draft.name,
            country_code=draft.country_code,
            currency_code=draft.currency_code,
            latest_version=1,
            created_by=user_id,
        )
    )
    version_id = await add_version(database, rule_id, 1, draft, user_id)
    result = await get_version(database, version_id)
    await database.commit()
    return result


async def locked_rule(database, rule_id, expected_version):
    row = (
        (
            await database.execute(
                select(rules).where(rules.c.id == rule_id).with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise failure(404, "RULE_NOT_FOUND", "Compensation rule not found.")
    if row["latest_version"] != expected_version:
        raise failure(
            409,
            "RULE_CHANGED",
            "This rule changed while you were editing. Reload it before saving.",
        )
    return row


async def publish_rule(
    database: AsyncSession, rule_id: UUID, draft: RulePublish, user_id: UUID
):
    row = await locked_rule(database, rule_id, draft.expected_version)
    if not row["active"]:
        raise failure(
            409,
            "RULE_INACTIVE",
            "Reactivate this rule before publishing a new version.",
        )
    if (row["country_code"], row["currency_code"]) != (
        draft.country_code,
        draft.currency_code,
    ):
        raise field_error(
            "country_code",
            "Country and currency are fixed for this rule. Create another rule to change them.",
        )
    number = row["latest_version"] + 1
    version_id = await add_version(database, rule_id, number, draft, user_id)
    await database.execute(
        update(rules)
        .where(rules.c.id == rule_id)
        .values(latest_version=number, name=draft.name)
    )
    result = await get_version(database, version_id)
    await database.commit()
    return result


async def set_rule_status(database: AsyncSession, rule_id: UUID, status: RuleStatus):
    await locked_rule(database, rule_id, status.expected_version)
    await database.execute(
        update(rules).where(rules.c.id == rule_id).values(active=status.active)
    )
    await database.commit()
    return await get_rule(database, rule_id)


async def read_package(
    database: AsyncSession, employee_id: int
) -> PackageResponse | None:
    columns = [column.label(f"line_{column.name}") for column in lines.c]
    rows = (
        (
            await database.execute(
                select(
                    packages,
                    versions.c.name.label("rule_name"),
                    versions.c.number.label("rule_number"),
                    *columns,
                )
                .select_from(
                    packages.outerjoin(
                        versions, packages.c.rule_version_id == versions.c.id
                    ).outerjoin(lines, packages.c.employee_id == lines.c.employee_id)
                )
                .where(packages.c.employee_id == employee_id)
                .order_by(lines.c.position)
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        if not await database.scalar(
            select(exists().where(employees.c.id == employee_id))
        ):
            raise missing_employee()
        return None
    components = []
    for row in rows:
        if row["line_code"] is not None:
            line = {column.name: row[f"line_{column.name}"] for column in lines.c}
            components.append(
                CalculatedComponent(
                    **line,
                    explanation="Fixed annual amount"
                    if line["method"] == "fixed"
                    else f"{decimal_text(line['value'])}% of annual basic pay",
                )
            )
    return PackageResponse(**rows[0], components=components)


async def preview_package(
    database: AsyncSession, employee_id: int, draft: PackageDraft, *, lock=False
):
    employee_query = select(employees.c.id, employees.c.country_code).where(
        employees.c.id == employee_id
    )
    if lock:
        employee_query = employee_query.with_for_update()
    employee = (await database.execute(employee_query)).mappings().one_or_none()
    if employee is None:
        raise missing_employee()
    if not await database.scalar(
        select(exists().where(currencies.c.code == draft.currency_code))
    ):
        raise field_error("currency_code", "Currency is unavailable.")
    components = draft.components
    if draft.rule_version_id:
        query = (
            select(rules).join(versions).where(versions.c.id == draft.rule_version_id)
        )
        if lock:
            query = query.with_for_update(read=True, of=rules)
        rule = (await database.execute(query)).mappings().one_or_none()
        if rule is None:
            raise field_error("rule_version_id", "Rule version is unavailable.")
        if (
            rule["country_code"] != employee["country_code"]
            or rule["currency_code"] != draft.currency_code
        ):
            raise field_error(
                "rule_version_id",
                "Choose a rule matching this employee's country and package currency.",
            )
        existing_version = await database.scalar(
            select(packages.c.rule_version_id).where(
                packages.c.employee_id == employee_id
            )
        )
        if not rule["active"] and existing_version != draft.rule_version_id:
            raise field_error(
                "rule_version_id",
                "This rule is inactive. Choose an active rule or enter components manually.",
            )
        components = (await get_version(database, draft.rule_version_id)).components
    try:
        return calculate(draft, components)
    except ValueError as error:
        raise field_error("components", str(error)) from None


async def save_package(
    database: AsyncSession, employee_id: int, draft: PackageSave, user_id: UUID
):
    calculation = await preview_package(database, employee_id, draft, lock=True)
    current = await database.scalar(
        select(packages.c.version).where(packages.c.employee_id == employee_id)
    )
    if (current or 0) != draft.expected_version:
        raise failure(
            409,
            "PACKAGE_CHANGED",
            "This package changed while you were editing. Your entries are kept. Reload the saved package before trying again.",
        )
    totals = calculation.model_dump(exclude={"components", "equity_status"})
    values = dict(
        employee_id=employee_id,
        version=(current or 0) + 1,
        effective_date=draft.effective_date,
        rule_version_id=draft.rule_version_id,
        updated_by=user_id,
        updated_at=func.clock_timestamp(),
        **totals,
    )
    statement = insert(packages).values(**values)
    await database.execute(
        statement.on_conflict_do_update(
            index_elements=[packages.c.employee_id], set_=values
        )
    )
    await database.execute(delete(lines).where(lines.c.employee_id == employee_id))
    if calculation.components:
        await database.execute(
            lines.insert(),
            [
                dict(
                    employee_id=employee_id,
                    position=position,
                    **line.model_dump(exclude={"explanation"}),
                )
                for position, line in enumerate(calculation.components)
            ],
        )
    await advance_report_revision(database)
    saved = await read_package(database, employee_id)
    await database.commit()
    return saved
