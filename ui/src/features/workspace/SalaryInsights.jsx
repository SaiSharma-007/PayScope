import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import SelectField from '../../components/SelectField'
import Skeleton from '../../components/Skeleton'
import { ErrorSummary } from '../compensation/Fields'
import { money, useReferenceData } from '../compensation/shared'
import { useWorkspaceReport } from './useWorkspaceReport'
import './reports.css'

const choices = (values) => values.map(([value, label]) => ({ value, label }))
const groupings = choices([
  ['country', 'Country'],
  ['department', 'Department'],
  ['job_title', 'Job title'],
])
const metrics = choices([
  ['basic', 'Basic pay'],
  ['guaranteed', 'Guaranteed cash and benefits'],
  ['target', 'Cash and benefits with targets'],
  ['equity', 'Annual equity cost'],
  ['ctc', 'Guaranteed annual CTC'],
  ['target_ctc', 'Annual CTC with targets'],
])
const number = new Intl.NumberFormat('en')
const percent = new Intl.NumberFormat('en', { maximumFractionDigits: 1 })
const nameOf = (row) => row.group_name || 'All employees'

function Ranges({ rows, currency }) {
  const [selected, setSelected] = useState(null)
  const eligible = rows.filter((row) => row.headcount)
  if (!eligible.length)
    return (
      <p className="comp-muted">No eligible compensation for this selection.</p>
    )
  const max = Math.max(...eligible.map((row) => Number(row.maximum)), 1)
  const position = (value) => (Number(value) / max) * 100
  return (
    <div className="report-ranges">
      <div className="range-axis">
        <div>
          <span>0 {currency}</span>
          <span>{money(max, currency)}</span>
        </div>
      </div>
      {eligible.map((row) => {
        const open = selected === row.group_id
        return (
          <div key={row.group_id} className="report-range-row">
            <button
              type="button"
              className="report-range-button"
              aria-expanded={open}
              onClick={() => setSelected(open ? null : row.group_id)}
            >
              <span>{nameOf(row)}</span>
              <span className="range-track" aria-hidden="true">
                <span
                  className="range-span"
                  style={{
                    left: `${position(row.minimum)}%`,
                    width: `${position(row.maximum) - position(row.minimum)}%`,
                  }}
                />
                <span
                  className="range-median"
                  style={{ left: `${position(row.median)}%` }}
                />
              </span>
              <strong>{money(row.median, currency)}</strong>
            </button>
            {open && (
              <p className="comp-muted">
                Range {money(row.minimum, currency)} to{' '}
                {money(row.maximum, currency)}. {number.format(row.headcount)}{' '}
                eligible employees.
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

function ReportTable({ rows, currency, skeletonRows = 0 }) {
  const columns = [
    ['minimum', 'Minimum'],
    ['median', 'Median'],
    ['maximum', 'Maximum'],
    ['mean', 'Mean'],
  ]
  return (
    <table className="report-table" role="table">
      <caption className="sr-only">
        {currency ? `Exact compensation figures in ${currency}` : 'Exact compensation figures'}
      </caption>
      <thead role="rowgroup">
        <tr role="row">
          <th scope="col">Group</th>
          {columns.map(([key, label]) => (
            <th key={key} scope="col">
              {label}
            </th>
          ))}
          <th scope="col">Eligible / in group</th>
        </tr>
      </thead>
      <tbody role="rowgroup" aria-hidden={skeletonRows ? true : undefined}>
        {skeletonRows
          ? Array.from({ length: skeletonRows }, (_, index) => (
              <tr key={index}>
                <th scope="row">
                  <Skeleton width="5rem" />
                </th>
                {columns.map(([key, label]) => (
                  <td key={key} data-label={label}>
                    <Skeleton width="5rem" />
                  </td>
                ))}
                <td data-label="Eligible / in group">
                  <Skeleton width="3rem" />
                </td>
              </tr>
            ))
          : rows.map((row) => (
              <tr key={row.group_id} role="row">
                <th scope="row" role="rowheader">
                  {nameOf(row)}
                </th>
                {columns.map(([key, label]) => (
                  <td role="cell" data-label={label} key={key}>
                    {row[key] == null ? '—' : money(row[key], currency)}
                  </td>
                ))}
                <td role="cell" data-label="Eligible / in group">
                  {number.format(row.headcount)} /{' '}
                  {number.format(row.population)}
                </td>
              </tr>
            ))}
      </tbody>
    </table>
  )
}

function ReportSkeleton({ previous }) {
  const panels = previous?.length ? previous : [{ rows: [] }]
  return panels.map(({ rows }, index) => (
    <section className="panel report-landscape" key={index}>
      <div className="comp-section-heading">
        <span className="skeleton-stack">
          <Skeleton width="14rem" height="1rem" />
          <Skeleton width="10rem" />
        </span>
      </div>
      <div className="report-ranges" aria-hidden="true">
        {Array.from({ length: Math.min(rows.length || 3, 4) }, (_, row) => (
          <div key={row} className="report-range-button">
            <Skeleton width="4rem" />
            <Skeleton height="7px" />
            <Skeleton width="5rem" />
          </div>
        ))}
      </div>
      <ReportTable skeletonRows={Math.min(rows.length || 4, 8)} />
    </section>
  ))
}

function Composition({ rows, withEquity }) {
  return (
    <div className="report-composition">
      {rows.map((row) => (
        <article
          key={`${row.country_code}:${row.currency_code}`}
          className="report-country"
        >
          <h3>
            {row.country_name} <span>{row.currency_code}</span>
          </h3>
          <p className="comp-muted">
            {number.format(row.eligible)}{' '}
            {withEquity ? 'with complete CTC' : 'with a saved package'} ·{' '}
            {number.format(row.population - row.eligible)} missing
          </p>
          {row.eligible > 0 && (
            <>
              <p className="country-cost">
                {money(row.total, row.currency_code)}
              </p>
              <div className="composition-bar" aria-hidden="true">
                {row.categories.map((category) => (
                  <span
                    key={category.category}
                    data-category={category.category}
                    style={{ flex: Number(category.amount) }}
                  />
                ))}
              </div>
              <ul>
                {row.categories.map((category) => (
                  <li key={category.category}>
                    <span>{category.label}</span>
                    <strong>{percent.format(category.share)}%</strong>
                  </li>
                ))}
              </ul>
              <details>
                <summary>Component details</summary>
                <ul>
                  {row.components.map((component) => (
                    <li
                      key={`${component.category}:${component.code}:${component.label}`}
                    >
                      <span>
                        {component.label}
                        <small>
                          {number.format(component.recorded)} recorded ·{' '}
                          {number.format(component.zero)} zero ·{' '}
                          {number.format(row.eligible - component.recorded)}{' '}
                          absent
                        </small>
                      </span>
                      <strong>
                        {money(component.amount, row.currency_code)}
                      </strong>
                    </li>
                  ))}
                </ul>
              </details>
            </>
          )}
        </article>
      ))}
    </div>
  )
}

export default function SalaryInsights() {
  const [params, setParams] = useSearchParams()
  const reference = useReferenceData()
  const query = new URLSearchParams()
  for (const key of [
    'country_code',
    'department_id',
    'job_title_id',
    'currency_code',
    'group_by',
    'metric',
    'year',
  ])
    if (params.get(key)) query.set(key, params.get(key))
  const { data, loading, error, retry } = useWorkspaceReport(
    `/analytics/compensation?${query}`,
  )
  const withEquity = ['equity', 'ctc', 'target_ctc'].includes(data?.metric)
  const currentYear = new Date().getFullYear()
  const filters = [
    [
      'country_code',
      'Country',
      reference.data?.countries,
      'code',
      'All countries',
    ],
    [
      'department_id',
      'Department',
      reference.data?.departments,
      'id',
      'All teams',
    ],
    [
      'job_title_id',
      'Job title',
      reference.data?.job_titles,
      'id',
      'All job titles',
    ],
    [
      'currency_code',
      'Currency',
      reference.data?.currencies,
      'code',
      'All currencies',
    ],
  ]
  function change(key, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next)
  }
  return (
    <main id="main" className="page workspace-preview-page">
      <div className="workspace-heading">
        <div>
          <h1>Salary insights</h1>
          <p>
            Compare annual compensation with a separate scale for each currency.
          </p>
        </div>
      </div>
      <section className="panel report-landscape" aria-label="Report filters">
        <div className="report-filters">
          <SelectField
            id="report-metric"
            label="Measure"
            options={metrics}
            value={params.get('metric') || 'guaranteed'}
            onChange={(value) => change('metric', value)}
          />
          <SelectField
            id="report-group"
            label="Group by"
            options={groupings}
            value={params.get('group_by') || 'country'}
            onChange={(value) => change('group_by', value)}
          />
          <label className="comp-field">
            Reporting year
            <input
              type="number"
              min="1900"
              max="9998"
              defaultValue={params.get('year') || currentYear}
              key={params.get('year')}
              onBlur={(event) => {
                if (
                  event.target.validity.valid &&
                  /^\d{4}$/.test(event.target.value)
                )
                  change('year', event.target.value)
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') event.currentTarget.blur()
              }}
            />
          </label>
          {filters.map(([key, label, items, field, placeholder]) => (
            <SelectField
              key={key}
              id={`report-${key}`}
              label={label}
              placeholder={placeholder}
              disabled={!reference.data}
              options={(items || []).map((item) => ({
                value: String(item[field]),
                label: key === 'currency_code' ? item.code : item.name,
              }))}
              value={params.get(key) || ''}
              onChange={(value) => change(key, value)}
            />
          ))}
        </div>
        <ErrorSummary error={reference.error} />
        {reference.error && (
          <button className="button secondary" onClick={reference.retry}>
            Retry filter options
          </button>
        )}
      </section>
      <p className="comp-status" role="status">
        {loading
          ? data
            ? 'Updating compensation report…'
            : 'Loading compensation report…'
          : error
            ? 'Report could not be updated.'
            : data
              ? `${number.format(data.employees)} employees matched · ${number.format(data.without_package)} without a saved package for this report`
              : ''}
      </p>
      <ErrorSummary error={error} />
      {error && (
        <button className="button secondary" onClick={retry}>
          Retry report
        </button>
      )}
      <div
        className="report-results"
        role="region"
        aria-label="Compensation report results"
        aria-busy={loading}
      >
        {loading ? (
          <ReportSkeleton previous={data?.currencies} />
        ) : (
          !error &&
          data && (
            <>
              {data.currencies.length === 0 && (
                <section className="panel report-landscape">
                  <h2>No compensation matches</h2>
                  <p className="comp-muted">
                    Try a different country, currency, or reporting year.
                  </p>
                </section>
              )}
              {data.currencies.map(({ currency_code, rows }) => (
                <section
                  key={`${data.metric}:${data.year}:${currency_code}`}
                  className="panel report-landscape"
                  aria-label={`${currency_code} compensation report`}
                >
                  <div className="comp-section-heading">
                    <div>
                      <h2>
                        {currency_code} ·{' '}
                        {
                          metrics.find((item) => item.value === data.metric)
                            ?.label
                        }
                      </h2>
                      <p>
                        {data.year} · Current packages effective by year end
                      </p>
                    </div>
                  </div>
                  <Ranges rows={rows} currency={currency_code} />
                  <ReportTable rows={rows} currency={currency_code} />
                </section>
              ))}
              {!!data.composition.length && (
                <section className="panel report-landscape">
                  <div className="comp-section-heading">
                    <div>
                      <h2>Cost composition by country</h2>
                      <p>
                        {withEquity
                          ? 'Share of guaranteed CTC for employees with complete costs for the selected year.'
                          : 'Share of guaranteed cash and benefit costs for employees with a saved package for this report.'}
                      </p>
                    </div>
                  </div>
                  <Composition
                    rows={data.composition}
                    withEquity={withEquity}
                  />
                </section>
              )}
            </>
          )
        )}
      </div>
    </main>
  )
}
