function salaryText(salary) {
  if (!salary) return 'Salary not entered'
  const [whole, fraction] = salary.annual_gross_base.split('.')
  return `${salary.currency_code} ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${(fraction || '').padEnd(2, '0')}`
}

export default function EmployeeTable({ employees }) {
  return (
    <table className="employee-table" role="table">
      <caption className="sr-only">
        Employee directory and current annual gross base salaries
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
            Annual base salary
          </th>
        </tr>
      </thead>
      <tbody role="rowgroup">
        {employees.map((employee) => (
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
              {employee.country_name}
            </td>
            <td
              role="cell"
              data-label="Annual base salary"
              className="salary-cell"
            >
              {salaryText(employee.salary)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
