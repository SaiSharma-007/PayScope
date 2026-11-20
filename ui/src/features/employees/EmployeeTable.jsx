import { money } from '../compensation/shared'
import { ChevronRight } from 'lucide-react'
import Skeleton from '../../components/Skeleton'

function EmployeeSkeletonRows({ count }) {
  return Array.from({ length: count }, (_, index) => (
    <tr key={index}>
      <td className="identity-cell">
        <span className="employee-identity">
          <Skeleton width="38px" height="38px" round />
          <span className="skeleton-stack">
            <Skeleton width="72%" />
            <Skeleton width="50%" height="0.6rem" />
          </span>
        </span>
      </td>
      <td data-label="Department / role">
        <span className="skeleton-stack">
          <Skeleton width="80%" />
          <Skeleton width="65%" height="0.6rem" />
        </span>
      </td>
      <td data-label="Country">
        <Skeleton width="4rem" />
      </td>
      <td className="salary-cell" data-label="Annual compensation">
        <span className="skeleton-stack">
          <Skeleton width="8.5rem" />
          <Skeleton width="7rem" height="0.6rem" />
        </span>
      </td>
      <td className="employee-action-cell">
        <Skeleton width="2rem" />
      </td>
    </tr>
  ))
}

export default function EmployeeTable({
  employees,
  onCompensation,
  skeletonRows = 0,
}) {
  return (
    <table className="employee-table" role="table">
      <caption className="sr-only">
        Employee directory and annual compensation
      </caption>
      <thead role="rowgroup">
        <tr role="row">
          <th scope="col" role="columnheader">
            Employee
          </th>
          <th scope="col" role="columnheader">
            Department / role
          </th>
          <th scope="col" role="columnheader">
            Country
          </th>
          <th scope="col" role="columnheader" className="salary-cell">
            Annual compensation
          </th>
          <th scope="col" role="columnheader" className="employee-action-cell">
            <span className="sr-only">Details</span>
          </th>
        </tr>
      </thead>
      <tbody role="rowgroup" aria-hidden={skeletonRows ? true : undefined}>
        {skeletonRows ? (
          <EmployeeSkeletonRows count={skeletonRows} />
        ) : (
          employees.map((employee) => (
            <tr key={employee.id} role="row">
              <td role="cell" className="identity-cell">
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
              </td>
              <td role="cell" data-label="Department / role">
                <span>
                  <strong>{employee.department_name}</strong>
                  <small>{employee.job_title}</small>
                </span>
              </td>
              <td role="cell" data-label="Country">
                <span className="employee-country">
                  {employee.country_name}
                </span>
              </td>
              <td
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
              </td>
              <td role="cell" className="employee-action-cell">
                <button
                  className="compensation-action"
                  type="button"
                  onClick={() => onCompensation(employee)}
                  aria-label={`Compensation for ${employee.full_name}`}
                  title="View compensation"
                >
                  <span>View</span>
                  <ChevronRight size={16} aria-hidden="true" />
                </button>
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  )
}
