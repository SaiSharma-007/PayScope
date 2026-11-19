from fastapi import APIRouter, Depends

from payscope.auth.router import VerifiedSession, require_session
from payscope.database import DatabaseSession
from payscope.employees.schemas import EmployeeId
from payscope.salaries import service
from payscope.salaries.schemas import SalaryResponse, SalaryUpdate

router = APIRouter(prefix="/employees/{employee_id}/salary", tags=["Salaries"])


@router.get("", dependencies=[Depends(require_session)])
async def get_salary(employee_id: EmployeeId, database: DatabaseSession) -> SalaryResponse | None:
    return await service.get_salary(database, employee_id)


@router.put("")
async def save_salary(
    employee_id: EmployeeId,
    salary: SalaryUpdate,
    session: VerifiedSession,
    database: DatabaseSession,
) -> SalaryResponse:
    return await service.save_salary(database, employee_id, salary, session.user_id)
