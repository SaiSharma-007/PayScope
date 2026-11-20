import { ArrowRight, Globe2, Users, Wallet } from 'lucide-react'
import { Link } from 'react-router-dom'
import { ErrorSummary } from '../compensation/Fields'
import { useWorkspaceReport } from './useWorkspaceReport'

const number = new Intl.NumberFormat('en')

export default function Overview() {
  const { data, loading, error, retry } = useWorkspaceReport(
    '/analytics/workforce-overview',
  )
  const metrics = data && [
    ['Employees', data.employees, Users],
    ['Countries', data.countries.length, Globe2],
    ['Saved compensation packages', data.packages, Wallet],
  ]
  return (
    <main id="main" className="page workspace-preview-page">
      <div className="workspace-heading">
        <div>
          <h1>Workforce overview</h1>
          <p>Employee coverage by country.</p>
        </div>
      </div>
      <ErrorSummary error={error} />
      {error && (
        <button type="button" className="button secondary" onClick={retry}>
          Try again
        </button>
      )}
      {loading && (
        <p className="comp-status" role="status">
          Loading workforce overview…
        </p>
      )}
      {data && (
        <>
          <div className="workspace-metrics">
            {metrics.map(([label, value, Icon]) => (
              <section className="panel workspace-metric" key={label}>
                <div>
                  <h2>{label}</h2>
                  <Icon size={19} aria-hidden="true" />
                </div>
                <strong>{number.format(value)}</strong>
              </section>
            ))}
          </div>
          <section
            className="panel report-landscape"
            aria-labelledby="country-coverage"
          >
            <div className="comp-section-heading">
              <div>
                <h2 id="country-coverage">Compensation coverage</h2>
                <p>Saved packages as a share of employees in each country.</p>
              </div>
            </div>
            {data.countries.length === 0 && <p>No employees are available.</p>}
            {data.countries.map((country) => (
              <Link
                className="coverage-row"
                to={`/insights?country_code=${country.country_code}`}
                key={country.country_code}
              >
                <strong>{country.country_name}</strong>
                <span>
                  {number.format(country.packages)} /{' '}
                  {number.format(country.employees)} employees
                </span>
                <ArrowRight size={17} aria-hidden="true" />
              </Link>
            ))}
          </section>
        </>
      )}
    </main>
  )
}
