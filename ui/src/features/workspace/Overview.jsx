import { useState } from 'react'
import { ArrowRight, ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Table, TableBody, TableCaption, TableCell, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { ErrorSummary } from '../compensation/Fields'
import { InsightHelp } from './InsightHelp'
import { useWorkspaceReport } from './useWorkspaceReport'
import './overview.css'

const number = new Intl.NumberFormat()
const percent = new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 1 })
const sources = [
  { key: 'packages', label: 'Package basic pay', short: 'Package' },
  { key: 'salary_only', label: 'Recorded salary only', short: 'Salary only' },
  { key: 'missing_pay', label: 'Missing base pay', short: 'Missing' },
]

function CoverageRail({ counts, maximum }) {
  return (
    <div className="overview-stacked-bar" aria-hidden="true">
      {sources.map(({ key }) => (
        <span key={key} data-source={key} style={{ flexBasis: `${maximum ? counts[key] / maximum * 100 : 0}%` }} />
      ))}
    </div>
  )
}

function OverviewSummary({ data, loading }) {
  const covered = data && data.packages + data.salary_only
  return (
    <Card className="overview-summary">
      <CardContent className="overview-summary-layout">
        <div className="overview-coverage">
          <strong>{loading ? <Skeleton className="h-16 w-32" /> : data.employees ? percent.format(covered / data.employees) : '—'}</strong>
          <div className="overview-help-heading">
            <h2>{!loading && !data.employees ? 'No pay records yet' : 'Base pay on file'}</h2>
            <InsightHelp label="Base pay on file">
              The share of employees with basic pay in a compensation package or a standalone salary record.
            </InsightHelp>
          </div>
          {!loading && <p>{number.format(covered)} of {number.format(data.employees)} employees</p>}
        </div>
        <div>
          <dl className="overview-summary-counts">
            {sources.map(({ key, label }) => (
              <div key={key}><dt>{label}</dt><dd>{loading ? <Skeleton className="h-7 w-12" /> : number.format(data[key])}</dd></div>
            ))}
          </dl>
          {!loading && <CoverageRail counts={data} maximum={data.employees} />}
        </div>
      </CardContent>
    </Card>
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
          <div className="overview-help-heading">
            <h2 id="overview-countries">Pay coverage by country</h2>
            <InsightHelp label="Pay coverage by country">
              People compares employee counts across countries. Share shows the percentage in each pay category within that country.
            </InsightHelp>
          </div>
          <p>{scale === 'people' ? 'Compare headcount and pay records across countries.' : 'Compare the share of employees in each pay category.'}</p>
        </div>
        <ToggleGroup type="single" value={scale} onValueChange={next => { if (next) setScale(next) }}
          className="overview-chart-control" aria-label="Country chart scale">
          <ToggleGroupItem value="people">People</ToggleGroupItem>
          <ToggleGroupItem value="share">Share</ToggleGroupItem>
        </ToggleGroup>
      </header>
      <div className="overview-chart-key">
        <ul className="overview-legend" aria-label="Pay categories">
          {sources.map(({ key, label }) => <li key={key}><i data-source={key} aria-hidden="true" />{label}</li>)}
        </ul>
        {ordered.length > 0 && <span>{scale === 'share' ? '0–100%' : `0–${number.format(largest)} employees`}</span>}
      </div>
      {loading ? (
        <div className="overview-country-loading" aria-hidden="true">
          {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-11 w-full" />)}
        </div>
      ) : !ordered.length ? <p className="overview-empty">Country coverage appears after employees are added.</p> : (
        <Table className="overview-country-table">
          <TableCaption className="sr-only">Pay coverage counts by country</TableCaption>
          <TableBody className="overview-country-list">
          {ordered.map((country) => (
            <TableRow key={country.country_code} role="row">
              <th scope="row" className="overview-country-name">
                <span className="overview-country-code" aria-hidden="true">{country.country_code}</span>
                <div><strong>{country.country_name}</strong><span>{number.format(country.employees)} employees</span></div>
              </th>
              <TableCell className="overview-country-data">
                <CoverageRail counts={country} maximum={scale === 'people' ? largest : country.employees} />
                <dl className="overview-country-counts">
                  {sources.map(({ key, short }) => (
                    <div key={key}><dt>{short}</dt><dd>{number.format(country[key])}</dd></div>
                  ))}
                </dl>
              </TableCell>
              <TableCell className="overview-country-actions"><Link className="overview-country-link" to={`/employees?country_code=${encodeURIComponent(country.country_code)}`} aria-label={`View employees in ${country.country_name}`}>
                <ArrowUpRight size={17} aria-hidden="true" />
              </Link></TableCell>
            </TableRow>
          ))}
          </TableBody>
        </Table>
      )}
    </section>
  )
}

function OverviewActions({ data }) {
  const missingCountries = data?.countries.filter((country) => country.missing_pay > 0)
    .sort((a, b) => b.missing_pay - a.missing_pay || a.country_name.localeCompare(b.country_name)) || []
  const missing = data?.missing_pay > 0
  return (
    <Card className="overview-attention" data-attention={missing}>
      <CardHeader>
            <div className="overview-help-heading">
              <h2>Needs attention</h2>
              <InsightHelp label="Needs attention">
                These employees have neither basic pay in a compensation package nor a standalone salary record.
              </InsightHelp>
            </div>
            <p><strong>{number.format(data.missing_pay)}</strong> {data.missing_pay === 1 ? 'employee needs' : 'employees need'} a base pay record.</p>
            <div className="overview-followup">
              <Button asChild className="overview-review">
                <Link to="/employees?pay_status=missing">Review missing pay <ArrowRight data-icon="inline-end" /></Link>
              </Button>
              <ul className="overview-attention-list">
                {missingCountries.slice(0, 3).map(country => (
                  <li key={country.country_code}>
                    <Link to={`/employees?country_code=${encodeURIComponent(country.country_code)}&pay_status=missing`}>
                      <span>{country.country_name}</span> <strong>{number.format(country.missing_pay)}</strong>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
      </CardHeader>
    </Card>
  )
}

export default function Overview() {
  const { data, loading, error, retry } = useWorkspaceReport('/analytics/workforce-overview')
  return (
    <main id="main" className="page overview-page">
      <header className="overview-heading">
        <h1 tabIndex={-1}>Workforce overview</h1>
        <nav aria-label="Workforce shortcuts">
          <Button asChild variant="link"><Link to="/employees">Manage employees</Link></Button>
          <Button asChild variant="link"><Link to="/insights">Salary insights</Link></Button>
          <Button asChild variant="link"><Link to="/insights/ask">Ask about pay</Link></Button>
        </nav>
      </header>
      <ErrorSummary error={error} />
      {error && <Button type="button" variant="outline" onClick={retry}>Try again</Button>}
      {loading && <p className="sr-only" role="status">Loading workforce overview…</p>}
      {(loading || data) && (
        <div className="overview-content" aria-busy={loading}>
          <div className="overview-sculpture" data-missing={Boolean(data?.missing_pay)}>
            <OverviewSummary data={data} loading={loading} />
            {data?.missing_pay > 0 && <OverviewActions data={data} />}
            {!loading && data.employees > 0 && data.missing_pay === 0 && (
              <p className="overview-complete">All base pay on file</p>
            )}
          </div>
          <CountryCoverage countries={data?.countries || []} loading={loading} />
        </div>
      )}
    </main>
  )
}
