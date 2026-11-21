import { useEffect, useId, useState } from 'react'
import SelectField from '../../components/SelectField'
import InsightChart from '../workspace/InsightChart'
import '../workspace/reports.css'

const measures = [
  { value: 'comparison', label: 'Average and median' },
  { value: 'mean', label: 'Average base pay' },
  { value: 'median', label: 'Median base pay' },
  { value: 'minimum', label: 'Minimum base pay' },
  { value: 'maximum', label: 'Maximum base pay' },
  { value: 'headcount', label: 'Employees with recorded pay' },
]
const columns = [
  ['Average', (row) => row.mean, 'money'],
  ['Median', (row) => row.median, 'money'],
  ['Minimum', (row) => row.minimum, 'money'],
  ['Maximum', (row) => row.maximum, 'money'],
  ['Employees', (row) => row.headcount, 'count'],
]

export default function ReportChart({ report, snapshot = true, onViewChange }) {
  const id = useId()
  const headcount = report.report_type === 'workforce_headcount'
  const [measure, setMeasure] = useState(report.chart_view?.measure || (report.metric === 'average' ? 'mean' : report.metric || 'comparison'))
  const [sort, setSort] = useState(report.chart_view?.sort || (report.operation === 'lowest' ? 'ascending' : 'descending'))
  useEffect(() => { onViewChange?.({ measure, sort }) }, [measure, sort, onViewChange])
  if (!report.rows.length) return null
  const metric = measure === 'comparison' ? 'mean' : measure
  const series = measure === 'comparison'
    ? [['mean', 'Average base pay'], ['median', 'Median base pay']]
    : [[measure, measures.find((item) => item.value === measure)?.label || measure]]
  const currencies = [...new Set(report.rows.map((row) => row.currency_code || report.currency_code))]
  return (
    <section className="agent-report-chart" aria-label="Interactive salary report">
      <div className="agent-chart-controls">
        <SelectField id={`${id}-measure`} label="Chart measure" value={measure} onChange={setMeasure} options={headcount ? [{ value: 'headcount', label: 'Total employees' }] : measures} />
        <SelectField id={`${id}-sort`} label="Chart order" value={sort} onChange={setSort} options={[
          { value: 'descending', label: 'Highest first' },
          { value: 'ascending', label: 'Lowest first' },
          { value: 'name', label: 'Group name' },
        ]} />
      </div>
      <p className="agent-chart-hint">Hover or focus for exact values. Click or tap to keep them open.</p>
      {currencies.map((currency) => {
        const rows = report.rows
          .filter((row) => (row.currency_code || report.currency_code) === currency)
          .map((row, index) => ({ ...row, group_id: row.evidence_id || `${currency}-${row.group_id ?? index}`, group_name: row.group_name || 'All matching employees', eligible: row.headcount }))
          .sort((a, b) => sort === 'name' ? a.group_name.localeCompare(b.group_name) : (Number(a[metric]) - Number(b[metric])) * (sort === 'ascending' ? 1 : -1))
        return (
          <div className="agent-chart-currency" key={currency || 'workforce'}>
            <strong>{measure === 'headcount' ? 'Employees' : currency} · {rows.length} {rows.length === 1 ? 'group' : 'groups'}</strong>
            <InsightChart key={`${currency}-${measure}-${sort}`} type="summary" rows={rows} currency={currency} series={headcount ? [['headcount', 'Total employees']] : series} columns={headcount ? [columns[4]] : columns} valueMode={measure === 'headcount' ? 'count' : 'money'} />
          </div>
        )
      })}
      <small>{snapshot ? `Saved report snapshot · revision ${report.revision}. Open report to check current values.` : `Current report · revision ${report.revision}.`}</small>
    </section>
  )
}
