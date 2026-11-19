from typing import Annotated

from fastapi import APIRouter, Depends, Query

from payscope.auth.router import require_session
from payscope.database import DatabaseSession
from payscope.employees import service
from payscope.employees.schemas import (
    EmployeeFilters,
    EmployeeId,
    EmployeePage,
    EmployeeResponse,
    ReferenceData,
)

router = APIRouter(tags=["Employees"], dependencies=[Depends(require_session)])


@router.get("/employees")
async def list_employees(
    filters: Annotated[EmployeeFilters, Query()], database: DatabaseSession
) -> EmployeePage:
    return await service.list_employees(database, filters)


@router.get("/employees/{employee_id}")
async def get_employee(employee_id: EmployeeId, database: DatabaseSession) -> EmployeeResponse:
    return await service.get_employee(database, employee_id)


@router.get("/reference-data")
async def get_reference_data(database: DatabaseSession) -> ReferenceData:
    return await service.get_reference_data(database)
