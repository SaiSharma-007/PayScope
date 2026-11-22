import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableCaption } from '../../components/ui/table'
import { Button } from '../../components/ui/button'
import { money } from '../compensation/shared'
import { ChevronRight } from 'lucide-react'
import Skeleton from '../../components/Skeleton'

function EmployeeSkeletonRows({ count }) {
  return Array.from({ length: count }, (_, index) => (
    <TableRow key={index}>
      <TableCell className="identity-cell">
        <span className="employee-identity">
          <Skeleton width="38px" height="38px" round />
          <span className="skeleton-stack">
            <Skeleton width="72%" />
            <Skeleton width="50%" height="0.6rem" />
          </span>
        </span>
      </TableCell>
      <TableCell data-label="Department / role">
        <span className="skeleton-stack">
          <Skeleton width="80%" />
          <Skeleton width="65%" height="0.6rem" />
        </span>
      </TableCell>
      <TableCell data-label="Country">
        <Skeleton width="4rem" />
      </TableCell>
      <TableCell className="salary-cell" data-label="Annual compensation">
        <span className="skeleton-stack">
          <Skeleton width="8.5rem" />
          <Skeleton width="7rem" height="0.6rem" />
        </span>
      </TableCell>
      <TableCell className="employee-action-cell">
        <Skeleton width="2rem" />
      </TableCell>
    </TableRow>
  ))
}

export default function EmployeeTable({
  employees,
  onCompensation,
  skeletonRows = 0,
}) {
  return (
    <Table className="employee-table" role="table">
      <TableCaption className="sr-only">
        Employee directory and annual compensation
      </TableCaption>
      <TableHeader role="rowgroup">
        <TableRow role="row">
          <TableHead scope="col" role="columnheader">
            Employee
          </TableHead>
          <TableHead scope="col" role="columnheader">
            Department / role
          </TableHead>
          <TableHead scope="col" role="columnheader">
            Country
          </TableHead>
          <TableHead scope="col" role="columnheader" className="salary-cell">
            Annual compensation
          </TableHead>
          <TableHead scope="col" role="columnheader" className="employee-action-cell">
            <span className="sr-only">Details</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody role="rowgroup" aria-hidden={skeletonRows ? true : undefined}>
        {skeletonRows ? (
          <EmployeeSkeletonRows count={skeletonRows} />
        ) : (
          employees.map((employee) => (
            <TableRow key={employee.id} role="row">
              <TableCell role="cell" className="identity-cell">
                <span className="employee-identity">
                  <span className="avatar" aria-hidden="true">
                    {employee.full_name
                      .split(' ')
                      .map((part) => part[0])
                      .slice(0, 2)
                      .join('')}
                  </span>
                  <span>
                    <strong>{employee.full_name}</strong>
                    <small className="employee-code">
                      {employee.employee_code}
                    </small>
                  </span>
                </span>
              </TableCell>
              <TableCell role="cell" data-label="Department / role">
                <span>
                  <strong>{employee.department_name}</strong>
                  <small>{employee.job_title}</small>
                </span>
              </TableCell>
              <TableCell role="cell" data-label="Country">
                <span className="employee-country">
                  {employee.country_name}
                </span>
              </TableCell>
              <TableCell
                role="cell"
                data-label="Annual compensation"
                className="salary-cell"
              >
                <span>
                  {employee.compensation
                    ? money(
                        employee.compensation.guaranteed_cost,
                        employee.compensation.currency_code,
                      )
                    : money(
                        employee.salary?.annual_gross_base,
                        employee.salary?.currency_code,
                      )}
                  <small>
                    {employee.compensation
                      ? 'Guaranteed cash & benefits'
                      : employee.salary
                        ? 'Legacy recorded total'
                        : 'No compensation record'}
                  </small>
                </span>
              </TableCell>
              <TableCell role="cell" className="employee-action-cell">
                <Button
                  className="compensation-action"
                  variant="secondary"
                  type="button"
                  onClick={() => onCompensation(employee)}
                  aria-label={`Compensation for ${employee.full_name}`}
                  title="View compensation"
                >
                  <span>View<span className="compensation-action-detail"> compensation</span></span>
                  <ChevronRight data-icon="inline-end" aria-hidden="true" />
                </Button>
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
