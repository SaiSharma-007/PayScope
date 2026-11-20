import {
  BarChart3,
  Boxes,
  ChartNoAxesColumn,
  ChartNoAxesGantt,
  Globe2,
  Layers3,
  LayoutGrid,
  Scale,
} from 'lucide-react'
import { money } from '../compensation/shared'

export const VIEWS = {
  pay_distribution: ['Pay distribution', ChartNoAxesGantt, 'range'],
  compensation_mix: ['Compensation mix', Layers3, 'mix'],
  country_comparison: ['Country comparison', Globe2, 'range', 'country'],
  guaranteed_vs_target_ctc: ['Guaranteed vs. target CTC', Scale, 'paired'],
  payroll_concentration: ['Payroll concentration', LayoutGrid, 'treemap'],
  role_bands: ['Role bands', Boxes, 'range', 'job_title'],
  equity_timeline: ['Equity timeline', ChartNoAxesColumn, 'timeline'],
  headcount_vs_payroll: ['Headcount vs. payroll', BarChart3, 'shares'],
}

export const GROUPS = {
  country: 'Country',
  department: 'Department',
  job_title: 'Job title',
}

export const METRICS = {
  basic: 'Basic pay',
  guaranteed: 'Guaranteed cash and benefits',
  target: 'Cash and benefits with targets',
  ctc: 'Guaranteed annual CTC',
  target_ctc: 'Annual CTC with targets',
}

export const CATEGORIES = {
  earning: 'Earnings',
  employer_cost: 'Employer costs',
  equity: 'Equity',
}

export const AWARDS = { rsu: 'RSUs', option: 'Stock options' }
export const PERCENTILES = ['p10', 'p25', 'p50', 'p75', 'p90']
export const count = new Intl.NumberFormat('en')
export const dash = '—'

export function metricChoices(type) {
  if (type === 'range') return ['basic', 'ctc', 'target_ctc']
  if (type === 'paired') return ['ctc']
  if (type === 'timeline') return []
  return ['guaranteed', 'target', 'ctc', 'target_ctc']
}

export function seriesFor(type, metric) {
  if (type === 'mix')
    return Object.entries(CATEGORIES).filter(
      ([key]) => key !== 'equity' || ['ctc', 'target_ctc'].includes(metric),
    )
  if (type === 'paired')
    return [
      ['guaranteed_ctc', 'Guaranteed CTC'],
      ['target_ctc', 'Target CTC'],
    ]
  if (type === 'shares')
    return [
      ['headcount_share', 'Headcount share'],
      ['payroll_share', 'Payroll share'],
    ]
  if (type === 'timeline') return Object.entries(AWARDS)
  return [
    ['box', 'P25–P75'],
    ['whisker', 'P10–P90'],
    ['median', 'Median'],
  ]
}

export function formatValue(value, type, currency) {
  if (value == null) return dash
  if (type === 'count') return count.format(value)
  if (type === 'share') return `${value}%`
  return money(value, currency)
}

const coverage = [
  ['Eligible', (row) => row.eligible, 'count'],
  ['Missing', (row) => row.missing, 'count'],
]

export function insightColumns(type, series) {
  const pay = (label, key) => [label, (row) => row[key], 'money']
  if (type === 'range')
    return [
      ...PERCENTILES.map((key) => [
        key.toUpperCase(),
        (row) => row.percentiles[key],
        'money',
      ]),
      pay('Spread', 'spread'),
      ...coverage,
    ]
  if (type === 'mix')
    return [
      ...series.map(([key, label]) => [
        label,
        (row) =>
          row.categories.find((category) => category.category === key)
            ?.amount ?? (row.eligible ? '0.00' : null),
        'money',
      ]),
      pay('Total', 'amount'),
      ...coverage,
    ]
  if (type === 'timeline')
    return [
      pay('Recorded cost', 'amount'),
      ['Recorded', (row) => row.eligible, 'count'],
      ['Recorded zero', (row) => row.recorded_zero, 'count'],
      ['Missing allocations', (row) => row.missing, 'count'],
    ]
  if (type === 'paired')
    return [...series.map(([key, label]) => pay(label, key)), ...coverage]
  return [
    pay('Payroll', 'amount'),
    ['Headcount', (row) => row.population, 'count'],
    ['Headcount share', (row) => row.headcount_share, 'share'],
    ['Payroll share', (row) => row.payroll_share, 'share'],
    ...coverage,
  ]
}
