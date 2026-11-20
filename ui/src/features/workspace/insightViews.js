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
  country_comparison: ['Country comparison', Globe2, 'country', 'country'],
  guaranteed_vs_target_ctc: ['Guaranteed vs. target CTC', Scale, 'paired'],
  payroll_concentration: ['Payroll concentration', LayoutGrid, 'treemap'],
  role_bands: ['Role bands', Boxes, 'range', 'job_title'],
  equity_timeline: ['Equity timeline', ChartNoAxesColumn, 'timeline'],
  headcount_vs_payroll: ['Headcount vs. payroll', BarChart3, 'shares'],
}

export const VIEW_HELP = {
  pay_distribution:
    'How does pay vary across the selected groups? The box shows the middle half, the diamond shows the median, and the whiskers run from P10 to P90.',
  compensation_mix:
    'What makes up the selected cost? Each segment shows the amount spent on earnings, employer costs, or equity where applicable.',
  country_comparison:
    'How does typical pay vary by country? Compare the median diamonds and the middle half of pay within each currency.',
  guaranteed_vs_target_ctc:
    'How much would company cost rise if target pay were earned? Both endpoints include recorded annual equity and use the same employees.',
  payroll_concentration:
    'Where is payroll concentrated? Larger tiles represent more payroll among the groups shown. Pin a tile to drill into departments or roles.',
  role_bands:
    'What does typical pay look like by job title? The box shows the middle half of eligible pay for each role.',
  equity_timeline:
    'How much equity cost was recorded each year? The lines show RSUs and stock options separately, with gaps where a total is unavailable.',
  headcount_vs_payroll:
    'Which groups account for a larger share of payroll than of employees? The distance between the dots shows the gap.',
}

const definitions = {
  'Insight view':
    'Choose the question you want the report to answer. Workforce filters apply to every view.',
  Measure:
    'Choose the amount to compare, such as basic pay or company cost including annual equity.',
  'Group by':
    'Choose how to split the matching employees. Group by department compares departments. The Department filter limits which employees are included.',
  Country: 'Include employees assigned to the selected country.',
  Department:
    'Include employees in one department. Group by department compares departments within the selection.',
  'Job title': 'Include employees with the selected job title.',
  Currency:
    'Limit the report to one recorded currency. Each currency has its own amounts and denominators.',
  'Reporting year':
    'Use packages effective by the end of this calendar year and equity allocations for the same year.',
  'Start year': 'The first calendar year included in the equity timeline.',
  'End year': 'The last calendar year included in the equity timeline.',
  Coverage:
    'The eligible count shows records that can be used for this measure. The missing count shows records that lacked required information.',
  Eligible:
    'Employees with enough recorded data to calculate the selected measure.',
  Missing:
    'Employees who matched the filters but lacked data required for the selected measure.',
  Headcount: 'All employees in this group with the displayed currency.',
  'Headcount share':
    'This group’s headcount divided by the full filtered headcount for this currency.',
  'Payroll share':
    'This group’s eligible payroll divided by the full filtered eligible payroll for this currency.',
  'Eligible payroll':
    'Total payroll for employees with complete values for the selected measure in this currency.',
  Payroll:
    'Total cost for eligible employees in this group, using the selected measure.',
  'Share gap': 'Payroll share minus headcount share, in percentage points.',
  'Guaranteed CTC':
    'Guaranteed cost to company. Add base pay, guaranteed allowances, employer-paid benefits, and recorded annual equity.',
  'Target CTC':
    'Company cost if employees earn their target incentives. Add target bonuses or commissions to guaranteed CTC for the same employees.',
  'At target':
    'Target CTC minus guaranteed CTC for the same employees and currency.',
  'P25–P75': 'The middle half of the group’s eligible pay values.',
  'P10–P90': 'The range from the 10th to the 90th percentile.',
  Median:
    'The 50th percentile. Half of eligible pay values are at or below it.',
  Spread: 'The highest eligible pay value minus the lowest eligible pay value.',
  Earnings:
    'Basic pay and included earnings components for the selected measure.',
  'Employer costs': 'Included benefits and other costs paid by the employer.',
  Equity: 'Annual allocations for applicable RSUs and stock options.',
  Total: 'Sum of the included components for the eligible employees.',
  RSUs: 'Restricted stock units. This series uses recorded annual allocations.',
  'Stock options':
    'Awards giving employees the right to purchase shares. This series uses recorded annual allocations.',
  'Recorded cost':
    'Sum of recorded amounts for this award type and year. A partial total excludes missing allocations.',
  Recorded:
    'Applicable awards with an allocation in the package currency, including recorded zeroes.',
  'Recorded zero':
    'Applicable awards with an explicit zero allocation for this year.',
  'Missing allocations':
    'Applicable awards without a usable allocation for this year.',
  'Allocation status':
    'Shows whether all, some, or none of the applicable awards have a recorded allocation.',
  'Year and award type': 'The calendar year and type of applicable award.',
}

export function helpFor(label) {
  return (
    definitions[label] ??
    (/^P\d+$/.test(label)
      ? `The ${label.slice(1)}th percentile of eligible pay values.`
      : undefined)
  )
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
  if (type === 'range' || type === 'country')
    return ['basic', 'ctc', 'target_ctc']
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
  if (type === 'treemap') return []
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
  if (type === 'points') return `${value} pp`
  if (type === 'text') return value
  return money(value, currency)
}

export function difference(left, right) {
  if (left == null || right == null) return null
  const hundredths = (value) => {
    const [whole, fraction = ''] = String(value).split('.')
    return BigInt(whole + fraction.padEnd(2, '0'))
  }
  const delta = hundredths(left) - hundredths(right)
  const digits = String(delta < 0n ? -delta : delta).padStart(3, '0')
  return `${delta < 0n ? '-' : ''}${digits.slice(0, -2)}.${digits.slice(-2)}`
}

export function equityStatus(row) {
  return (
    row.coverage_status ??
    (!row.eligible ? 'missing' : row.missing ? 'partial' : 'complete')
  )
}

export function reportReading(type, rows, currency) {
  const pay = (amount) => formatValue(amount, 'money', currency)
  if (type === 'timeline') {
    const row = rows.findLast((item) => item.amount != null)
    if (!row) return null
    const partial =
      equityStatus(row) === 'partial' ? ' This total is partial.' : ''
    return `In ${row.year}, recorded ${row.kind === 'rsu' ? 'RSU' : 'stock option'} cost was ${pay(row.amount)}.${partial}`
  }
  const row = rows.find((item) =>
    type === 'shares' ? item.payroll_share != null : item.eligible > 0,
  )
  if (!row) return null
  const name = row.group_name
  if (type === 'shares') {
    const gap = difference(row.payroll_share, row.headcount_share)
    return `${name} accounts for ${row.headcount_share}% of employees and ${row.payroll_share}% of eligible payroll in this ${currency} selection. The payroll share is ${Number(gap) === 0 ? 'equal to the headcount share' : `${gap.replace(/^-/, '')} percentage points ${Number(gap) < 0 ? 'lower' : 'higher'}`}.`
  }
  if (type === 'paired') {
    const delta = difference(row.target_ctc, row.guaranteed_ctc)
    return Number(delta) === 0
      ? `${name} has equal guaranteed and target CTC of ${pay(row.guaranteed_ctc)} for the eligible employees.`
      : `${name} would cost ${pay(delta)} more at target for the same eligible employees.`
  }
  if (type === 'mix')
    return `${name} totals ${pay(row.amount)} across the included components.`
  if (type === 'treemap')
    return `${name} accounts for ${row.payroll_share}% of eligible payroll in this ${currency} selection.`
  return type === 'country'
    ? `${name} has a median of ${pay(row.percentiles.p50)} and a pay spread of ${pay(row.spread)} across ${count.format(row.eligible)} eligible employees.`
    : `The middle half of eligible pay in ${name} runs from ${pay(row.percentiles.p25)} to ${pay(row.percentiles.p75)}.`
}

const coverage = [
  ['Eligible', (row) => row.eligible, 'count'],
  ['Missing', (row) => row.missing, 'count'],
]

export function insightColumns(type, series) {
  const pay = (label, key) => [label, (row) => row[key], 'money']
  if (type === 'range' || type === 'country')
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
      [
        'Allocation status',
        (row) =>
          ({ complete: 'Complete', partial: 'Partial', missing: 'Missing' })[
            equityStatus(row)
          ],
        'text',
      ],
    ]
  if (type === 'paired')
    return [
      ...series.map(([key, label]) => pay(label, key)),
      [
        'At target',
        (row) => difference(row.target_ctc, row.guaranteed_ctc),
        'money',
      ],
      ...coverage,
    ]
  return [
    pay('Payroll', 'amount'),
    ['Headcount', (row) => row.population, 'count'],
    ['Headcount share', (row) => row.headcount_share, 'share'],
    ['Payroll share', (row) => row.payroll_share, 'share'],
    ...(type === 'shares'
      ? [
          [
            'Share gap',
            (row) => difference(row.payroll_share, row.headcount_share),
            'points',
          ],
        ]
      : []),
    ...coverage,
  ]
}
