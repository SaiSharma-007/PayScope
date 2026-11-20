import { useEffect, useRef, useState } from 'react'
import {
  ArrowRight,
  ChevronRight,
  RotateCw,
  SlidersHorizontal,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import SelectField from '../../components/SelectField'
import Skeleton from '../../components/Skeleton'
import { ErrorSummary } from '../compensation/Fields'
import { useReferenceData } from '../compensation/shared'
import InsightChart from './InsightChart'
import { InsightHelp } from './InsightHelp'
import {
  AWARDS,
  CATEGORIES,
  GROUPS,
  METRICS,
  VIEWS,
  VIEW_HELP,
  count,
  formatValue,
  helpFor,
  insightColumns,
  metricChoices,
  reportReading,
  seriesFor,
} from './insightViews'
import { useWorkspaceReport } from './useWorkspaceReport'

const dimensions = [
  ['country_code', 'Country', 'countries', 'code', 'All countries'],
  ['department_id', 'Department', 'departments', 'id', 'All departments'],
  ['job_title_id', 'Job title', 'job_titles', 'id', 'All job titles'],
  ['currency_code', 'Currency', 'currencies', 'code', 'All currencies'],
]
const viewOptions = Object.entries(VIEWS).map(([value, [label]]) => ({
  value,
  label,
}))
const optionsFor = (keys, labels) =>
  keys.map((value) => ({ value, label: labels[value] }))
const groupOptions = optionsFor(Object.keys(GROUPS), GROUPS)
const validYear = (value, min, max) =>
  /^\d{4}$/.test(value) && Number(value) >= min && Number(value) <= max

function DefinedLabel({ label, children }) {
  return (
    <span className="insight-defined">
      {children ?? label}
      <InsightHelp label={label}>{helpFor(label)}</InsightHelp>
    </span>
  )
}

const exclusionLabels = {
  no_effective_package: 'Without a package effective by year-end',
  equity_unconfigured: 'Without an equity status',
  missing_allocation: 'Missing a usable award allocation',
}

function exclusionList(reasons) {
  return Object.entries(exclusionLabels)
    .filter(([key]) => reasons?.[key] > 0)
    .map(([key, label]) => [label, count.format(reasons[key])])
}

function InsightSelect({ label, ...props }) {
  return (
    <div className="insight-select-help">
      <SelectField label={label} {...props} />
      <InsightHelp label={label}>{helpFor(label)}</InsightHelp>
    </div>
  )
}

function YearField({ id, label, value, min = 1900, max = 9998, onChange }) {
  const [invalid, setInvalid] = useState(false)
  return (
    <div className="comp-field">
      <DefinedLabel label={label}>
        <label htmlFor={id}>{label}</label>
      </DefinedLabel>
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        defaultValue={value}
        inputMode="numeric"
        enterKeyHint="done"
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? `${id}-error` : undefined}
        onBlur={(event) => {
          const next = event.currentTarget.value
          const valid = validYear(next, min, max)
          setInvalid(!valid)
          if (valid && next !== String(value)) onChange(next)
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter') event.currentTarget.blur()
        }}
      />
      {invalid && (
        <small id={`${id}-error`} className="error-message">
          Enter a year from {min} to {max}.
        </small>
      )}
    </div>
  )
}

function ViewPicker({ insight, viewSearch, onChange }) {
  return (
    <>
      <nav className="insight-view-grid" aria-label="Salary insight views">
        {Object.entries(VIEWS).map(([key, [label, Icon]]) => (
          <div className="insight-view-choice" key={key}>
            <Link
              to={{ search: viewSearch(key) }}
              aria-current={insight === key ? 'page' : undefined}
            >
              <Icon size={18} strokeWidth={1.75} aria-hidden="true" />
              <span>{label}</span>
            </Link>
            <InsightHelp label={label}>{VIEW_HELP[key]}</InsightHelp>
          </div>
        ))}
      </nav>
      <div className="insight-view-select">
        <InsightSelect
          id="insight-view"
          label="Insight view"
          value={insight}
          options={viewOptions}
          onChange={onChange}
        />
      </div>
    </>
  )
}

function Components({ row, currency }) {
  if (!row.components.length) return null
  return (
    <details className="insight-components">
      <summary>Components</summary>
      <ul>
        {row.components.map((line) => (
          <li key={`${line.category}:${line.commitment}:${line.code}`}>
            <span>
              {line.label}
              <small>
                {CATEGORIES[line.category]} · {line.commitment}
                {line.component_count > 1
                  ? ` · ${line.component_count} codes`
                  : ''}
              </small>
            </span>
            <strong>{formatValue(line.amount, 'money', currency)}</strong>
          </li>
        ))}
      </ul>
    </details>
  )
}

function InsightTable({
  rows,
  columns,
  currency,
  type,
  grouping,
  loading,
  onDrill,
  drillLabel,
}) {
  const timeline = type === 'timeline'
  const groupLabel = timeline ? 'Year and award type' : GROUPS[grouping]
  return (
    <div className="insight-table-wrap">
      <table className="report-table" role="table">
        <caption className="sr-only">
          {currency ? `Exact values in ${currency}` : 'Exact values'}
        </caption>
        <thead role="rowgroup">
          <tr role="row">
            <th scope="col">
              {loading ? groupLabel : <DefinedLabel label={groupLabel} />}
            </th>
            {columns.map(([label]) => (
              <th key={label} scope="col">
                {loading ? label : <DefinedLabel label={label} />}
              </th>
            ))}
          </tr>
        </thead>
        <tbody role="rowgroup" aria-hidden={loading || undefined}>
          {loading
            ? Array.from({ length: 4 }, (_, index) => (
                <tr key={index} role="row">
                  <th scope="row" role="rowheader">
                    <Skeleton width="5.5rem" />
                  </th>
                  {columns.map(([label]) => (
                    <td key={label} role="cell" data-label={label}>
                      <Skeleton width="4rem" />
                    </td>
                  ))}
                </tr>
              ))
            : rows.map((row) => (
                <tr
                  key={timeline ? `${row.year}:${row.kind}` : row.group_id}
                  role="row"
                >
                  <th scope="row" role="rowheader">
                    {timeline ? (
                      <>
                        {row.year} · {AWARDS[row.kind]}
                      </>
                    ) : (
                      row.group_name
                    )}
                    {type === 'mix' && (
                      <Components row={row} currency={currency} />
                    )}
                    {onDrill && (
                      <button
                        type="button"
                        className="insight-text-button insight-table-drill"
                        aria-label={`${drillLabel} in ${row.group_name}`}
                        onClick={() => onDrill(row)}
                      >
                        {drillLabel} <ArrowRight size={14} aria-hidden="true" />
                      </button>
                    )}
                  </th>
                  {columns.map(([label, read, mode]) => (
                    <td role="cell" data-label={label} key={label}>
                      {formatValue(read(row), mode, currency)}
                      {label === 'Missing' &&
                        row.missing > 0 &&
                        row.missing_reasons && (
                          <InsightHelp
                            label={`missing CTC in ${row.group_name}`}
                          >
                            {exclusionList(row.missing_reasons)
                              .map(
                                ([reason, value]) =>
                                  `${value} ${reason.toLowerCase()}`,
                              )
                              .join(' · ')}
                          </InsightHelp>
                        )}
                    </td>
                  ))}
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  )
}

function ReportSkeleton({ type, columns, grouping }) {
  return (
    <section className="panel insight-panel" aria-hidden="true">
      <div className="skeleton-stack">
        <Skeleton width="5rem" height="1.5rem" />
        <Skeleton width="15rem" />
      </div>
      <div className="insight-chart-placeholder" data-type={type}>
        {Array.from({ length: 3 }, (_, index) => (
          <Skeleton key={index} height="1rem" />
        ))}
      </div>
      <InsightTable type={type} grouping={grouping} columns={columns} loading />
    </section>
  )
}

function CTCCoverage({ reasons }) {
  const exclusions = exclusionList(reasons)
  if (!exclusions.length) return null
  return (
    <div className="insight-exclusions">
      <strong>Why some employees are excluded</strong>
      <ul>
        {exclusions.map(([label, value]) => (
          <li key={label}>
            {label} <b>{value}</b>
          </li>
        ))}
      </ul>
      <Link to="/employees">Review employee compensation and equity</Link>
    </div>
  )
}

function CurrencyReport({
  currency,
  report,
  type,
  columns,
  series,
  onDrill,
  drillLabel,
}) {
  const code = currency.currency_code
  const timeline = type === 'timeline'
  const eligible = timeline
    ? currency.rows.reduce((sum, row) => sum + row.eligible, 0)
    : currency.eligible
  const missing = timeline
    ? currency.rows.reduce((sum, row) => sum + row.missing, 0)
    : currency.missing
  const ready = timeline || eligible > 0 || type === 'shares'
  const reading = ready ? reportReading(type, currency.rows, code) : null
  const period =
    timeline && report.start_year !== report.year
      ? `${report.start_year}–${report.year}`
      : report.year
  return (
    <section className="panel insight-panel" aria-label={`${code} report`}>
      <div className="insight-panel-heading">
        <div>
          <h3>
            {code} <span>{period}</span>
          </h3>
          <p className="insight-panel-coverage">
            {timeline
              ? `${count.format(eligible)} recorded · ${count.format(missing)} missing ${missing === 1 ? 'allocation' : 'allocations'}`
              : `${count.format(eligible)} of ${count.format(currency.population)} ${currency.population === 1 ? 'employee' : 'employees'} eligible · ${count.format(missing)} missing`}
            <InsightHelp label="Coverage">
              {timeline
                ? 'Coverage counts applicable award allocations across the displayed years. An award can count in more than one year.'
                : helpFor('Coverage')}
            </InsightHelp>
          </p>
        </div>
        {currency.payroll_total != null && (
          <div className="insight-total">
            <DefinedLabel label="Eligible payroll" />
            <strong>
              {formatValue(currency.payroll_total, 'money', code)}
            </strong>
          </div>
        )}
      </div>
      {!ready && !currency.missing_reasons && (
        <p className="insight-incomplete">
          No complete values for this selection.{' '}
          <Link to="/employees">Review employee compensation</Link> or adjust
          the filters.
        </p>
      )}
      <CTCCoverage reasons={currency.missing_reasons} />
      {timeline && missing > 0 && (
        <p className="insight-incomplete">
          Partial totals include the recorded allocations. A gap means a total
          is unavailable or no awards applied.{' '}
          <Link to="/employees">Review missing allocations</Link>.
        </p>
      )}
      {reading && <p className="insight-reading">{reading}</p>}
      {type === 'country' &&
        eligible > 0 &&
        currency.rows.filter((row) => row.eligible > 0).length === 1 && (
          <p className="insight-coverage-note">
            One country has eligible pay in {code} for these filters.
          </p>
        )}
      {type === 'shares' && eligible === 0 && (
        <p className="insight-incomplete">
          Payroll is unavailable for these groups.{' '}
          <Link to="/employees">Review employee compensation</Link> or adjust
          the filters.
        </p>
      )}
      {ready && (
        <InsightChart
          type={type}
          rows={currency.rows}
          currency={code}
          columns={columns}
          series={series}
          startYear={report.start_year}
          year={report.year}
          onDrill={onDrill}
          drillLabel={drillLabel}
        />
      )}
      {currency.group_count > currency.rows.length && (
        <p className="insight-coverage-note">
          Showing {count.format(currency.rows.length)} of{' '}
          {count.format(currency.group_count)} groups. Narrow the filters to see
          more.
        </p>
      )}
      <div className="insight-table-heading">
        <h4>Exact values</h4>
        {missing > 0 && <small>— indicates an unavailable value</small>}
      </div>
      <details className="insight-column-help">
        <summary>Column definitions</summary>
        <dl>
          {columns.map(([label]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{helpFor(label)}</dd>
            </div>
          ))}
        </dl>
      </details>
      <InsightTable
        rows={currency.rows}
        columns={columns}
        currency={code}
        type={type}
        grouping={report.group_by}
        onDrill={onDrill}
        drillLabel={drillLabel}
      />
    </section>
  )
}

export default function SalaryInsights() {
  const [params, setParams] = useSearchParams()
  const reference = useReferenceData()
  const pageTitle = useRef(null)
  const reportTitle = useRef(null)
  useEffect(() => {
    if (document.activeElement === document.body)
      pageTitle.current.focus({ preventScroll: true })
  }, [])
  const requested = params.get('insight')
  const insight = Object.hasOwn(VIEWS, requested)
    ? requested
    : 'pay_distribution'
  const [title, , type, fixedGroup] = VIEWS[insight]
  const timeline = type === 'timeline'
  const metrics = metricChoices(type)
  const requestedMetric = params.get('metric')
  const metric = metrics.includes(requestedMetric)
    ? requestedMetric
    : metrics[0]
  const requestedGroup = params.get('group_by')
  const grouping =
    fixedGroup ||
    (Object.hasOwn(GROUPS, requestedGroup) ? requestedGroup : 'country')
  const requestedYear = params.get('year')
  const year = validYear(requestedYear, 1900, 9998)
    ? Number(requestedYear)
    : new Date().getFullYear()
  const requestedStart = params.get('start_year')
  const minStart = Math.max(1900, year - 19)
  const startYear = validYear(requestedStart, minStart, year)
    ? Number(requestedStart)
    : Math.max(1900, year - 4)
  const query = new URLSearchParams({ insight, year })
  const selectedDimensions = dimensions.filter(([key]) => params.get(key))
  for (const [key] of selectedDimensions) query.set(key, params.get(key))
  const scope = selectedDimensions.map(([key, label, collection, field]) => {
    const value = params.get(key)
    if (key === 'currency_code') return value
    const option = reference.data?.[collection]?.find(
      (item) => String(item[field]) === value,
    )
    return option?.name ?? (field === 'code' ? value : label)
  })
  if (timeline) query.set('start_year', startYear)
  else {
    query.set('group_by', grouping)
    query.set('metric', metric)
  }
  const path = `/analytics/salary-insights?${query}`
  const { data, error, loading, retry } = useWorkspaceReport(path)
  const series = seriesFor(type, metric)
  const columns = insightColumns(type, series)
  const canDrill = type === 'treemap' && grouping !== 'job_title'
  const drillLabel = grouping === 'country' ? 'View departments' : 'View roles'
  const drillDepth = type === 'treemap' ? (params.get('drill') ?? '') : ''
  const drillLevels = drillDepth.split('.')
  const inCountry =
    drillLevels.includes('country') && params.get('country_code')
  const inDepartment =
    drillLevels.includes('department') && params.get('department_id')

  function change(key, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (['group_by', 'country_code', 'department_id'].includes(key))
      next.delete('drill')
    if (next.toString() !== params.toString()) setParams(next)
  }

  function viewParams(view) {
    if (view === insight) return params
    const next = new URLSearchParams(params)
    const [, , nextType] = VIEWS[view]
    next.set('insight', view)
    next.delete('drill')
    if (!metricChoices(nextType).includes(requestedMetric))
      next.delete('metric')
    return next
  }

  function drill(row) {
    const next = new URLSearchParams(params)
    if (grouping === 'country') {
      next.set('country_code', row.group_id)
      next.set('group_by', 'department')
      next.set('drill', 'country')
    } else {
      next.set('department_id', row.group_id)
      next.set('group_by', 'job_title')
      next.set('drill', inCountry ? 'country.department' : 'department')
    }
    setParams(next)
    reportTitle.current.focus()
  }

  function ancestorSearch(level) {
    const next = new URLSearchParams(params)
    if (inDepartment) next.delete('department_id')
    if (level === 'country' && inCountry) next.delete('country_code')
    next.set('group_by', level)
    if (level === 'department' && inCountry && inDepartment)
      next.set('drill', 'country')
    else next.delete('drill')
    return `?${next}`
  }

  function clearFilters() {
    const next = new URLSearchParams(params)
    for (const [key] of dimensions) next.delete(key)
    if (drillDepth) next.delete('group_by')
    next.delete('drill')
    setParams(next)
  }

  const countryLabel =
    reference.data?.countries.find((item) => item.code === inCountry)?.name ??
    inCountry
  const departmentLabel =
    reference.data?.departments.find((item) => String(item.id) === inDepartment)
      ?.name ?? inDepartment
  const status = loading
    ? 'Loading report…'
    : error
      ? 'Report could not be loaded.'
      : data
        ? `${count.format(data.employees)} ${data.employees === 1 ? 'employee' : 'employees'} matched${data.without_currency ? ` · ${count.format(data.without_currency)} without a recorded currency` : ''}`
        : ''

  return (
    <main id="main" className="page workspace-preview-page salary-insights">
      <div className="workspace-heading insight-heading">
        <div>
          <h1 ref={pageTitle} tabIndex={-1}>
            Salary insights
          </h1>
          <p>Explore pay, payroll, and equity across your workforce.</p>
        </div>
        <button
          type="button"
          className="button secondary insight-refresh"
          aria-label="Refresh report"
          disabled={loading}
          onClick={retry}
        >
          <RotateCw size={16} aria-hidden="true" />
          <span>Refresh report</span>
        </button>
      </div>

      <section className="panel insight-controls" aria-label="Report controls">
        <ViewPicker
          insight={insight}
          viewSearch={(view) => `?${viewParams(view)}`}
          onChange={(view) => {
            if (view !== insight) setParams(viewParams(view))
          }}
        />
        <div className="insight-primary-fields report-filters">
          {!timeline && type !== 'paired' && (
            <InsightSelect
              id="insight-metric"
              label="Measure"
              value={metric}
              options={optionsFor(metrics, METRICS)}
              onChange={(value) => change('metric', value)}
            />
          )}
          {!timeline && !fixedGroup && (
            <InsightSelect
              id="insight-group"
              label="Group by"
              value={grouping}
              options={groupOptions}
              onChange={(value) => change('group_by', value)}
            />
          )}
          {timeline && (
            <YearField
              id="insight-start"
              key={`start:${startYear}:${year}`}
              label="Start year"
              value={startYear}
              min={minStart}
              max={year}
              onChange={(value) => change('start_year', value)}
            />
          )}
          <YearField
            id="insight-year"
            key={year}
            label={timeline ? 'End year' : 'Reporting year'}
            value={year}
            onChange={(value) => change('year', value)}
          />
        </div>
        <details className="insight-filters">
          <summary>
            <SlidersHorizontal size={16} aria-hidden="true" /> Workforce filters
            {scope.length > 0 && <span>{scope.join(' · ')}</span>}
            <ChevronRight size={16} aria-hidden="true" />
          </summary>
          <div className="report-filters">
            {dimensions.map(([key, label, collection, field, placeholder]) => (
              <InsightSelect
                key={key}
                id={`insight-${key}`}
                label={label}
                placeholder={placeholder}
                disabled={!reference.data}
                value={params.get(key) ?? ''}
                options={(reference.data?.[collection] ?? []).map((item) => ({
                  value: String(item[field]),
                  label: key === 'currency_code' ? item.code : item.name,
                }))}
                onChange={(value) => change(key, value)}
              />
            ))}
          </div>
          <ErrorSummary error={reference.error} />
          {reference.error && (
            <button
              type="button"
              className="button secondary"
              onClick={reference.retry}
            >
              Retry filter options
            </button>
          )}
          {selectedDimensions.length > 0 && (
            <button
              type="button"
              className="insight-text-button"
              onClick={clearFilters}
            >
              Clear workforce filters
            </button>
          )}
        </details>
      </section>

      <section
        aria-labelledby="insight-report-title"
        className="insight-report"
      >
        <div className="insight-report-heading">
          <div>
            <h2 id="insight-report-title" ref={reportTitle} tabIndex={-1}>
              {title}
            </h2>
            <p className="insight-view-description">{VIEW_HELP[insight]}</p>
            <p role="status">{status}</p>
          </div>
          {(inCountry || inDepartment) && (
            <nav className="insight-breadcrumb" aria-label="Payroll drill-down">
              <ol>
                <li>
                  <Link
                    className="insight-text-button"
                    to={{
                      search: ancestorSearch(
                        inCountry ? 'country' : 'department',
                      ),
                    }}
                    onClick={() => reportTitle.current.focus()}
                  >
                    {inCountry ? 'Countries' : 'Departments'}
                  </Link>
                </li>
                {inCountry && (
                  <li>
                    <ChevronRight size={14} aria-hidden="true" />
                    {inDepartment ? (
                      <Link
                        className="insight-text-button"
                        to={{ search: ancestorSearch('department') }}
                        onClick={() => reportTitle.current.focus()}
                      >
                        {countryLabel}
                      </Link>
                    ) : (
                      <span aria-current="page">{countryLabel}</span>
                    )}
                  </li>
                )}
                {inDepartment && (
                  <li>
                    <ChevronRight size={14} aria-hidden="true" />
                    <span aria-current="page">{departmentLabel}</span>
                  </li>
                )}
              </ol>
            </nav>
          )}
        </div>
        <div className="report-results" aria-busy={loading}>
          {loading ? (
            <ReportSkeleton type={type} columns={columns} grouping={grouping} />
          ) : error ? (
            <div className="panel insight-panel">
              <ErrorSummary error={error} />
              <button
                type="button"
                className="button secondary"
                onClick={retry}
              >
                Retry report
              </button>
            </div>
          ) : data?.currencies.length === 0 ? (
            <div className="panel insight-panel insight-empty">
              <h3>
                {timeline
                  ? 'No recorded equity awards match'
                  : 'No compensation matches'}
              </h3>
              <p>
                {timeline
                  ? 'This selection has no applicable awards in the chosen years. Review employee awards or change the years and filters.'
                  : 'Try another reporting year or adjust the workforce filters.'}
              </p>
              {selectedDimensions.length > 0 && (
                <button
                  type="button"
                  className="button secondary"
                  onClick={clearFilters}
                >
                  Clear workforce filters
                </button>
              )}
              {timeline && <Link to="/employees">Review employee equity</Link>}
            </div>
          ) : (
            data?.currencies.map((currency) => (
              <CurrencyReport
                key={`${path}:${currency.currency_code}`}
                currency={currency}
                report={data}
                type={type}
                columns={columns}
                series={series}
                onDrill={canDrill ? drill : null}
                drillLabel={drillLabel}
              />
            ))
          )}
        </div>
      </section>
    </main>
  )
}
