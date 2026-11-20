from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from payscope.auth.router import VerifiedSession, require_session
from payscope.compensation import equity, service
from payscope.compensation.calculator import calculate
from payscope.compensation.equity_schemas import AwardDraft
from payscope.compensation.schemas import (
    PackageDraft,
    PackageResponse,
    PackageSave,
    RuleDraft,
    RulePublish,
    RuleStatus,
    RuleVersion,
)
from payscope.database import DatabaseSession
from payscope.employees.schemas import EmployeeId

router = APIRouter(tags=["Compensation"])
EquityYear = Annotated[int, Query(ge=1900, le=9998)]


@router.get("/employees/{employee_id}/equity", dependencies=[Depends(require_session)])
async def employee_equity(
    employee_id: EmployeeId, database: DatabaseSession, year: EquityYear | None = None
):
    return await equity.equity_details(database, employee_id, year or date.today().year)


@router.post("/employees/{employee_id}/equity/awards", status_code=201)
async def create_award(
    employee_id: EmployeeId,
    draft: AwardDraft,
    session: VerifiedSession,
    database: DatabaseSession,
):
    return await equity.save_award(database, employee_id, draft, session.user_id)


@router.put("/employees/{employee_id}/equity/awards/{award_id}")
async def update_award(
    employee_id: EmployeeId,
    award_id: UUID,
    draft: AwardDraft,
    session: VerifiedSession,
    database: DatabaseSession,
):
    return await equity.save_award(
        database, employee_id, draft, session.user_id, award_id
    )


@router.put("/employees/{employee_id}/equity/not-applicable", status_code=204)
async def no_equity(
    employee_id: EmployeeId, session: VerifiedSession, database: DatabaseSession
):
    await equity.mark_no_equity(database, employee_id, session.user_id)


@router.post("/compensation/preview")
async def preview_rule(draft: PackageDraft, session: VerifiedSession):
    if draft.rule_version_id:
        raise service.field_error(
            "rule_version_id", "Use employee preview to apply a saved rule."
        )
    try:
        return calculate(draft, draft.components)
    except ValueError as error:
        raise service.field_error("components", str(error)) from None


@router.get("/compensation/rules", dependencies=[Depends(require_session)])
async def list_rules(
    database: DatabaseSession,
    country_code: Annotated[str | None, Query(pattern=r"^[A-Z]{2}$")] = None,
    currency_code: Annotated[str | None, Query(pattern=r"^(INR|USD|GBP|EUR)$")] = None,
    active: bool | None = None,
    page: Annotated[int, Query(ge=1, le=2147483647)] = 1,
):
    return await service.list_rules(database, country_code, currency_code, active, page)


@router.post("/compensation/rules", status_code=201)
async def create_rule(
    draft: RuleDraft, session: VerifiedSession, database: DatabaseSession
) -> RuleVersion:
    return await service.create_rule(database, draft, session.user_id)


@router.get("/compensation/rules/{rule_id}", dependencies=[Depends(require_session)])
async def get_rule(rule_id: UUID, database: DatabaseSession):
    return await service.get_rule(database, rule_id)


@router.post("/compensation/rules/{rule_id}/versions", status_code=201)
async def publish_rule(
    rule_id: UUID,
    draft: RulePublish,
    session: VerifiedSession,
    database: DatabaseSession,
) -> RuleVersion:
    return await service.publish_rule(database, rule_id, draft, session.user_id)


@router.patch("/compensation/rules/{rule_id}")
async def set_rule_status(
    rule_id: UUID,
    status: RuleStatus,
    session: VerifiedSession,
    database: DatabaseSession,
):
    return await service.set_rule_status(database, rule_id, status)


@router.get(
    "/compensation/versions/{version_id}", dependencies=[Depends(require_session)]
)
async def get_version(version_id: UUID, database: DatabaseSession) -> RuleVersion:
    return await service.get_version(database, version_id)


@router.get(
    "/employees/{employee_id}/compensation", dependencies=[Depends(require_session)]
)
async def read_package(
    employee_id: EmployeeId, database: DatabaseSession
) -> PackageResponse | None:
    return await service.read_package(database, employee_id)


@router.post("/employees/{employee_id}/compensation/preview")
async def preview_package(
    employee_id: EmployeeId,
    draft: PackageDraft,
    session: VerifiedSession,
    database: DatabaseSession,
):
    return await service.preview_package(database, employee_id, draft)


@router.put("/employees/{employee_id}/compensation")
async def save_package(
    employee_id: EmployeeId,
    draft: PackageSave,
    session: VerifiedSession,
    database: DatabaseSession,
) -> PackageResponse:
    return await service.save_package(database, employee_id, draft, session.user_id)
