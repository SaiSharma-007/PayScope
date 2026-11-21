import { useState } from 'react'
import {
  ArrowRight, ArrowUpRight, ChartNoAxesCombined,
  CircleAlert, CircleCheck, Globe2, MessageSquare, Users, Wallet,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import Skeleton from '../../components/Skeleton'
import { ErrorSummary } from '../compensation/Fields'
import { useWorkspaceReport } from './useWorkspaceReport'
import './overview.css'

const number = new Intl.NumberFormat()
const percent = new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 1 })
const sources = [
  { key: 'packages', label: 'Package basic pay', short: 'Package' },
  { key: 'salary_only', label: 'Recorded salary only', short: 'Salary only' },
  { key: 'missing_pay', label: 'Missing base pay', short: 'Missing' },
]

function OverviewHero({ coverage, loading, countryCount }) {
  return (
    <header className="overview-hero">
      <div className="overview-intro">
        {countryCount > 0 && <p className="overview-geography"><Globe2 size={15} aria-hidden="true" /> {number.format(countryCount)} {countryCount === 1 ? 'country' : 'countries'}</p>}
        <h1 tabIndex={-1}>Workforce overview</h1>
        <p>See where pay is on file and which employee records need a closer look.</p>
        <div className="overview-hero-actions">
          <Link className="overview-hero-primary" to="/employees">Manage employees <ArrowRight size={17} aria-hidden="true" /></Link>
          <Link className="overview-hero-secondary" to="/insights/ask"><MessageSquare size={16} aria-hidden="true" /> Ask about pay</Link>
        </div>
      </div>
      <div className="overview-orbit">
        <div className="overview-gauge" style={{ '--coverage': `${(coverage ?? 0) * 100}%` }}>
          <div className="overview-gauge-center">
            <strong>{loading ? <Skeleton width="4rem" height="1.75rem" /> : coverage == null ? '—' : percent.format(coverage)}</strong>
            <span>Base pay coverage</span>
          </div>
        </div>
      </div>
    </header>
  )
}

function OverviewMetrics({ data, loading }) {
  const metrics = [
    { label: 'Employees', value: data?.employees, icon: Users, to: '/employees' },
    { label: 'Base pay on file', value: data && data.packages + data.salary_only, icon: CircleCheck, to: '/employees?pay_status=recorded' },
    { label: 'Missing base pay', value: data?.missing_pay, icon: CircleAlert, to: '/employees?pay_status=missing' },
    { label: 'Saved packages', value: data?.packages, icon: Wallet },
  ]
  return (
    <dl className="overview-metrics" aria-label="Pay data summary">
      {metrics.map(({ label, value, icon: Icon, to }) => (
        <div key={label}>
          <dt>{to ? <Link to={to}>{label}<ArrowUpRight size={13} aria-hidden="true" /></Link> : label}</dt>
          <dd>{loading ? <Skeleton width="3.5rem" height="1.5rem" /> : number.format(value)}</dd>
          <Icon size={18} className="overview-metric-icon" aria-hidden="true" />
        </div>
      ))}
    </dl>
  )
}

function CountryCoverage({ countries, loading }) {
  const [scale, setScale] = useState('people')
  const ordered = [...countries].sort((a, b) => b.employees - a.employees || a.country_name.localeCompare(b.country_name))
  const largest = ordered[0]?.employees || 1
  return (
    <section className="panel overview-country-panel" aria-labelledby="overview-countries">
      <header className="overview-panel-heading">
        <div>
          <h2 id="overview-countries">Pay coverage by country</h2>
          <p>{scale === 'people' ? 'Compare headcount and pay records across countries.' : 'Compare the share of employees in each pay category.'}</p>
        </div>
        <div className="overview-chart-control" role="group" aria-label="Country chart scale">
          <button type="button" aria-pressed={scale === 'people'} onClick={() => setScale('people')}>People</button>
          <button type="button" aria-pressed={scale === 'share'} onClick={() => setScale('share')}>Share</button>
        </div>
      </header>
      <div className="overview-chart-key">
        <ul className="overview-legend" aria-label="Pay categories">
          {sources.map(({ key, label }) => <li key={key}><i data-source={key} aria-hidden="true" />{label}</li>)}
        </ul>
        {ordered.length > 0 && <span>{scale === 'share' ? '0–100%' : `0–${number.format(largest)} employees`}</span>}
      </div>
      {loading ? (
        <div className="overview-country-loading" aria-hidden="true">
          {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} height="2.75rem" />)}
        </div>
      ) : !ordered.length ? <p className="overview-empty">Country coverage appears after employees are added.</p> : (
        <ul className="overview-country-list">
          {ordered.map((country) => (
            <li key={country.country_code}>
              <div className="overview-country-name">
                <span className="overview-country-code" aria-hidden="true">{country.country_code}</span>
                <div><strong>{country.country_name}</strong><span>{number.format(country.employees)} employees</span></div>
              </div>
              <div className="overview-country-data">
                <div className="overview-stacked-bar" aria-hidden="true">
                  {sources.map(({ key }) => <span key={key} data-source={key} style={{ width: `${country[key] / (scale === 'people' ? largest : country.employees) * 100}%` }} />)}
                </div>
                <dl className="overview-country-counts">
                  {sources.map(({ key, short }) => (
                    <div key={key}><dt>{short}</dt><dd>{number.format(country[key])}</dd></div>
                  ))}
                </dl>
              </div>
              <Link className="overview-country-link" to={`/employees?country_code=${encodeURIComponent(country.country_code)}`} aria-label={`View employees in ${country.country_name}`}>
                <ArrowUpRight size={17} aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function OverviewActions({ data, loading }) {
  const missingCountries = data?.countries.filter((country) => country.missing_pay > 0)
    .sort((a, b) => b.missing_pay - a.missing_pay || a.country_name.localeCompare(b.country_name)) || []
  const missing = data?.missing_pay > 0
  return (
    <aside className="overview-sidebar" aria-label="Pay coverage follow-up">
      <section className="panel overview-attention" data-attention={missing}>
        <span className="overview-attention-icon" aria-hidden="true">{missing ? <CircleAlert size={20} /> : <CircleCheck size={20} />}</span>
        {loading ? <><Skeleton width="8rem" height="1.25rem" /><Skeleton height="0.875rem" /></> : missing ? (
          <>
            <h2>Needs attention</h2>
            <p><strong>{number.format(data.missing_pay)}</strong> {data.missing_pay === 1 ? 'employee needs' : 'employees need'} a base pay record.</p>
            <ul className="overview-attention-list">
              {missingCountries.slice(0, 3).map((country) => (
                <li key={country.country_code}>
                  <Link to={`/employees?country_code=${encodeURIComponent(country.country_code)}&pay_status=missing`}>
                    <span>{country.country_name}</span><strong>{number.format(country.missing_pay)}</strong><ArrowUpRight size={14} aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
            <Link className="overview-text-link" to="/employees?pay_status=missing">View all employees missing pay <ArrowRight size={15} aria-hidden="true" /></Link>
          </>
        ) : (
          <>
            <h2>{data.employees ? 'All base pay on file' : 'No pay records yet'}</h2>
            <p>{data.employees ? 'Every employee has basic pay in a package or a recorded salary.' : 'Pay coverage appears when employee records are available.'}</p>
          </>
        )}
      </section>
      <Link className="panel overview-insights-link" to="/insights">
        <span className="overview-insights-icon"><ChartNoAxesCombined size={20} aria-hidden="true" /></span>
        <span><strong>Salary insights</strong><small>Compare pay by country, team or role.</small></span>
        <ArrowUpRight className="overview-insights-arrow" size={19} aria-hidden="true" />
      </Link>
    </aside>
  )
}

export default function Overview() {
  const { data, loading, error, retry } = useWorkspaceReport('/analytics/workforce-overview')
  const coverage = data?.employees ? (data.employees - data.missing_pay) / data.employees : null
  return (
    <main id="main" className="page overview-page">
      <OverviewHero coverage={coverage} loading={loading} countryCount={data?.countries.length} />
      <ErrorSummary error={error} />
      {error && <button type="button" className="button secondary overview-retry" onClick={retry}>Try again</button>}
      {loading && <p className="sr-only" role="status">Loading workforce overview…</p>}
      {(loading || data) && (
        <div className="overview-content" aria-busy={loading}>
          <OverviewMetrics data={data} loading={loading} />
          <div className="overview-detail-grid">
            <CountryCoverage countries={data?.countries || []} loading={loading} />
            <OverviewActions data={data} loading={loading} />
          </div>
        </div>
      )}
    </main>
  )
}
