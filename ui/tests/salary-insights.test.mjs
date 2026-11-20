import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { after, before, test } from 'node:test'
import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { chromium } from 'playwright'

const port = process.env.PAYSCOPE_TEST_PORT || '4176'
const origin = `http://localhost:${port}`
const liveApi = process.env.PAYSCOPE_LIVE_API_URL
const snapshots = process.env.PAYSCOPE_INSIGHTS_SCREENSHOTS
let browser
let server

const departments = [
  { id: 1, name: 'Engineering' },
  {
    id: 2,
    name: 'International workforce operations and organizational development',
  },
]
const countries = [
  { code: 'IN', name: 'India' },
  { code: 'US', name: 'United States' },
  { code: 'DE', name: 'Germany' },
]
const roles = [{ id: 3, name: 'Senior engineer' }]
const session = {
  user: { id: 'hr', email: 'hr@example.test', display_name: 'HR Manager' },
  csrf_token: 'fixture',
  expires_at: new Date(Date.now() + 3_600_000).toISOString(),
}
const pay = {
  p10: '80.00',
  p25: '90.00',
  p50: '100.00',
  p75: '120.00',
  p90: '145.00',
}

before(async () => {
  server = spawn(
    process.execPath,
    ['node_modules/vite/bin/vite.js', '--port', port, '--strictPort'],
    { stdio: 'ignore' },
  )
  for (let attempt = 0; ; attempt++) {
    if (server.exitCode !== null || attempt === 100)
      throw new Error(
        `Salary Insights test server did not start on port ${port}.`,
      )
    if (
      await fetch(origin)
        .then((response) => response.ok)
        .catch(() => false)
    )
      break
    await delay(100)
  }
  browser = await chromium.launch({
    executablePath: process.env.PAYSCOPE_CHROME_PATH || undefined,
  })
})

after(async () => {
  await browser?.close()
  server?.kill()
})

function fixture(query) {
  const insight = query.get('insight')
  const country = query.get('country_code')
  const groupBy = query.get('group_by')
  const isTimeline = insight === 'equity_timeline'
  const year = Number(query.get('year'))
  const start = Number(query.get('start_year'))
  const rows =
    groupBy === 'job_title'
      ? roles
      : groupBy === 'department'
        ? departments
        : countries.slice(0, 2)
  const currencies = [
    ['IN', 'INR'],
    ['US', 'USD'],
  ]
    .filter(
      ([id, code]) =>
        (!country || id === country) &&
        (!query.has('currency_code') || query.get('currency_code') === code),
    )
    .map(([id, code]) => ({
      currency_code: code,
      population: 10,
      eligible: 8,
      missing: 2,
      group_count: groupBy === 'department' ? 3 : rows.length,
      ...(['payroll_concentration', 'headcount_vs_payroll'].includes(insight)
        ? { payroll_total: '1500.00' }
        : {}),
      rows: isTimeline
        ? [
            {
              year: start,
              kind: 'option',
              eligible: 1,
              recorded_zero: 1,
              missing: 1,
              amount: '0.00',
            },
            {
              year: start,
              kind: 'rsu',
              eligible: 3,
              recorded_zero: 0,
              missing: 0,
              amount: '75.00',
            },
            {
              year,
              kind: 'rsu',
              eligible: 0,
              recorded_zero: 0,
              missing: 2,
              amount: null,
            },
          ]
        : rows
            .filter((row) => !row.code || row.code === id)
            .map((row, index) => ({
              group_id: String(row.id ?? row.code),
              group_name: row.name,
              population: 6,
              eligible: 5,
              missing: 1,
              percentiles: pay,
              spread: '95.00',
              guaranteed_ctc: '1000.00',
              target_ctc: '1200.00',
              amount: index ? '250.00' : '1172.25',
              headcount_share: '60.00',
              payroll_share: index ? '16.67' : '78.15',
              categories: [
                { category: 'earning', amount: '900.00' },
                { category: 'employer_cost', amount: '272.25' },
              ],
              components: [
                {
                  category: 'earning',
                  commitment: 'guaranteed',
                  code: 'basic_pay',
                  label: 'Basic pay',
                  amount: '900.00',
                  component_count: 1,
                },
                {
                  category: 'employer_cost',
                  commitment: 'guaranteed',
                  code: 'insurance',
                  label: 'Insurance',
                  amount: '272.25',
                  component_count: 1,
                },
              ],
            })),
    }))
  return {
    revision: 5,
    insight,
    year,
    start_year: isTimeline ? start : null,
    group_by: groupBy,
    metric: query.get('metric'),
    employees: country === 'DE' ? 0 : country ? 10 : 20,
    without_currency: 0,
    currencies,
  }
}

async function snapshot(page, name) {
  if (!snapshots) return
  await mkdir(snapshots, { recursive: true })
  await page.screenshot({
    path: join(snapshots, `${name}.png`),
    animations: 'disabled',
  })
}

async function withFixture(run, options = {}) {
  const { handle, ...contextOptions } = options
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    ...contextOptions,
  })
  const page = await context.newPage()
  page.setDefaultTimeout(8000)
  const errors = []
  const requests = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/auth/session')
      return route.fulfill({ json: session })
    if (url.pathname === '/api/reference-data') {
      return route.fulfill({
        json: {
          countries,
          departments,
          job_titles: roles,
          currencies: [{ code: 'INR' }, { code: 'USD' }],
        },
      })
    }
    assert.equal(url.pathname, '/api/analytics/salary-insights')
    requests.push(url.searchParams)
    if (await handle?.(route, url.searchParams)) return
    await route.fulfill({ json: fixture(url.searchParams) }).catch(() => {})
  })
  try {
    await run(page, requests)
    assert.deepEqual(errors, [])
  } finally {
    await context.close()
  }
}

const table = (page, currency = 'INR') =>
  page.getByRole('table', { name: `Exact values in ${currency}` })
const selected = (page, currency = 'INR') =>
  page
    .getByRole('region', { name: `${currency} report` })
    .getByRole('region', { name: 'Selected values' })

function nextReport(page, key, value) {
  return page.waitForResponse((response) => {
    const url = new URL(response.url())
    return (
      response.ok() &&
      url.pathname === '/api/analytics/salary-insights' &&
      url.searchParams.get(key) === value
    )
  })
}

async function select(page, field, label) {
  await page.getByRole('combobox', { name: field, exact: true }).click()
  await page.getByRole('option', { name: label, exact: true }).click()
}

test('shared filters, all eight views, and keyboard and pointer chart values', async () => {
  await withFixture(async (page, requests) => {
    await page.goto(
      `${origin}/insights?year=2026&country_code=IN&group_by=department`,
    )
    await table(page)
      .getByRole('cell', { name: 'INR 100.00', exact: true })
      .first()
      .waitFor()
    const longName = departments[1].name
    const second = page.getByRole('button', { name: new RegExp(longName) })
    await second.focus()
    await second.press('Enter')
    assert.equal(await second.getAttribute('aria-expanded'), 'true')
    assert.match(
      await selected(page).innerText(),
      /organizational development[\s\S]*INR 145\.00/,
    )
    await page.keyboard.press('Escape')
    await selected(page).waitFor({ state: 'hidden' })
    await page.getByRole('button', { name: /^Engineering/ }).hover()
    assert.match(
      await page.getByRole('tooltip', { name: 'Selected values' }).innerText(),
      /^Engineering/,
    )
    await snapshot(page, 'distribution-desktop')

    await Promise.all([
      nextReport(page, 'metric', 'ctc'),
      select(page, 'Measure', 'Guaranteed annual CTC'),
    ])
    await table(page).waitFor()
    assert.equal(requests.at(-1).get('metric'), 'ctc')
    await page.getByText('Workforce filters', { exact: false }).first().click()
    await Promise.all([
      nextReport(page, 'currency_code', 'INR'),
      select(page, 'Currency', 'INR'),
    ])
    await table(page).waitFor()
    assert.equal(new URL(page.url()).searchParams.get('currency_code'), 'INR')

    for (const [view, viewId, exact] of [
      ['Compensation mix', 'compensation_mix', 'INR 1,172.25'],
      ['Country comparison', 'country_comparison', 'INR 100.00'],
      ['Guaranteed vs. target CTC', 'guaranteed_vs_target_ctc', 'INR 1,200.00'],
      ['Payroll concentration', 'payroll_concentration', '78.15%'],
      ['Role bands', 'role_bands', 'INR 145.00'],
      ['Headcount vs. payroll', 'headcount_vs_payroll', '60.00%'],
      ['Equity timeline', 'equity_timeline', 'INR 0.00'],
    ]) {
      await Promise.all([
        nextReport(page, 'insight', viewId),
        page.getByRole('link', { name: view, exact: true }).click(),
      ])
      await table(page)
        .getByRole('cell', { name: exact, exact: true })
        .first()
        .waitFor()
      assert.equal(requests.at(-1).get('insight'), viewId)
      assert.equal(requests.at(-1).get('country_code'), 'IN')
      assert.equal(requests.at(-1).get('currency_code'), 'INR')
      if (viewId === 'compensation_mix') {
        await table(page)
          .getByText('Components', { exact: true })
          .first()
          .click()
        await table(page)
          .getByText('Insurance', { exact: false })
          .first()
          .waitFor()
      }
      if (viewId === 'equity_timeline') {
        await table(page)
          .getByRole('row', { name: /2026 · RSUs.*—.*2/ })
          .waitFor()
        await page.getByRole('button', { name: '2026', exact: true }).click()
        assert.match(
          await selected(page).innerText(),
          /Missing allocations\s*2/,
        )
        assert.equal(
          await page.locator('.insight-timeline [data-series="rsu"]').count(),
          1,
        )
      }
      if (viewId === 'headcount_vs_payroll') {
        await table(page).getByRole('cell', { name: '18.15 pp' }).waitFor()
        await page.getByText(/18\.15 percentage points higher/).waitFor()
      }
      if (viewId === 'guaranteed_vs_target_ctc') {
        await table(page)
          .getByRole('cell', { name: 'INR 200.00' })
          .first()
          .waitFor()
      }
      if (viewId === 'country_comparison') {
        await page.locator('.insight-country-point').waitFor()
      }
    }
  })
})

test('payroll drill-down, browser back, and bookmarks preserve report state', async () => {
  await withFixture(async (page, requests) => {
    await page.goto(
      `${origin}/insights?insight=payroll_concentration&year=2026&currency_code=INR`,
    )
    await table(page).waitFor()
    await page
      .getByRole('button', { name: /India, 78\.15% of payroll/ })
      .click()
    await selected(page).waitFor()
    await page.keyboard.press('Tab')
    await page.keyboard.press('Tab')
    assert.match(
      await page.evaluate(() => document.activeElement.textContent),
      /View departments/,
    )
    await page.keyboard.press('Enter')
    await table(page)
      .getByRole('rowheader', { name: /Engineering/ })
      .waitFor()
    assert.equal(requests.at(-1).get('country_code'), 'IN')
    assert.equal(requests.at(-1).get('group_by'), 'department')
    await table(page)
      .getByRole('button', { name: 'View roles in Engineering' })
      .click()
    await table(page)
      .getByRole('rowheader', { name: 'Senior engineer' })
      .waitFor()
    const deepLink = page.url()
    assert.equal(new URL(deepLink).searchParams.get('department_id'), '1')
    await page.reload()
    await table(page)
      .getByRole('rowheader', { name: 'Senior engineer' })
      .waitFor()
    const breadcrumbs = page.getByRole('navigation', {
      name: 'Payroll drill-down',
    })
    await breadcrumbs.getByText('Engineering').waitFor()
    await breadcrumbs.getByRole('link', { name: 'India' }).click()
    await table(page)
      .getByRole('rowheader', { name: /Engineering/ })
      .waitFor()
    await page.goBack()
    await table(page)
      .getByRole('rowheader', { name: 'Senior engineer' })
      .waitFor()
    assert.equal(page.url(), deepLink)
    await breadcrumbs.getByRole('link', { name: 'Countries' }).click()
    await table(page).getByRole('rowheader', { name: /India/ }).waitFor()
    assert.equal(new URL(page.url()).searchParams.has('country_code'), false)
  })
})

test('skeletons block stale rows, late requests lose, and errors can retry', async () => {
  let release
  let releaseReturn
  const slow = new Promise((resolve) => {
    release = resolve
  })
  const returning = new Promise((resolve) => {
    releaseReturn = resolve
  })
  let holdReturn = false
  let fail = false
  try {
    await withFixture(
      async (page) => {
        await page.goto(`${origin}/insights?year=2026`)
        await table(page).waitFor()
        await page.getByText('Workforce filters', { exact: true }).click()
        await select(page, 'Country', 'India')
        await page.getByRole('status').getByText('Loading report…').waitFor()
        assert.equal(await table(page).count(), 0)
        assert.equal(
          await page.locator('.insight-chart-placeholder .skeleton').count(),
          3,
        )
        assert(
          (await page.locator('[aria-busy=true] tbody .skeleton').count()) > 0,
        )
        holdReturn = true
        await page.goBack()
        await page.locator('.insight-chart-placeholder').waitFor()
        assert.equal(await table(page).count(), 0)
        await select(page, 'Country', 'United States')
        await table(page, 'USD').waitFor()
        release()
        releaseReturn()
        await page
          .getByRole('spinbutton', { name: 'Reporting year' })
          .fill('1899')
        await page
          .getByRole('spinbutton', { name: 'Reporting year' })
          .press('Enter')
        await page.getByText('Enter a year from 1900 to 9998.').waitFor()
        assert.equal(new URL(page.url()).searchParams.get('year'), '2026')
        assert.equal(await table(page).count(), 0)

        fail = true
        await page.getByRole('button', { name: 'Refresh report' }).click()
        await page
          .getByText('Couldn’t connect. Check your connection and try again.')
          .waitFor()
        fail = false
        await page.getByRole('button', { name: 'Retry report' }).click()
        await table(page, 'USD').waitFor()
        await select(page, 'Country', 'Germany')
        await page
          .getByRole('heading', { name: 'No compensation matches' })
          .waitFor()
        await page
          .locator('.insight-empty')
          .getByRole('button', { name: 'Clear workforce filters' })
          .click()
        await table(page).waitFor()
        await table(page, 'USD').waitFor()
      },
      {
        handle: async (route, query) => {
          if (query.get('country_code') === 'IN') await slow
          if (holdReturn && !query.has('country_code')) await returning
          if (!fail) return false
          await route.abort('failed')
          return true
        },
      },
    )
  } finally {
    release()
    releaseReturn()
  }
})

test('help and chart details remain near their anchors in long reports', async () => {
  await withFixture(
    async (page) => {
      await page.goto(
        `${origin}/insights?year=2026&country_code=IN&group_by=department`,
      )
      await table(page).waitFor()
      const help = page.getByRole('button', {
        name: 'About Group by',
        exact: true,
      })
      await help.focus()
      const helpCard = page.getByRole('tooltip', { name: 'About Group by' })
      await helpCard.getByText(/Department filter limits/).waitFor()
      await page.keyboard.press('Escape')
      await helpCard.waitFor({ state: 'hidden' })

      for (const name of ['Team 1', 'Team 20']) {
        const mark = page.getByRole('button', {
          name: new RegExp(`^${name} INR`),
        })
        await mark.hover()
        const tooltip = page.getByRole('tooltip', { name: 'Selected values' })
        await tooltip.getByText(name, { exact: true }).waitFor()
        const bounds = await tooltip.boundingBox()
        const anchor = await mark.boundingBox()
        assert(bounds.x >= 0 && bounds.x + bounds.width <= 1100)
        assert(bounds.y >= 0 && bounds.y + bounds.height <= 700)
        assert(
          Math.min(
            Math.abs(bounds.y - anchor.y - anchor.height),
            Math.abs(bounds.y + bounds.height - anchor.y),
          ) < 20,
        )
        await mark.click()
        await selected(page)
          .getByRole('button', { name: 'Close details' })
          .waitFor()
        await page.keyboard.press('Tab')
        assert.equal(
          await page.evaluate(() =>
            document.activeElement.getAttribute('aria-label'),
          ),
          'Close details',
        )
        if (name === 'Team 1') await page.keyboard.press('Escape')
        else await page.mouse.click(4, 650)
        await selected(page).waitFor({ state: 'hidden' })
      }
    },
    {
      viewport: { width: 1100, height: 700 },
      handle: async (route, query) => {
        const result = fixture(query)
        const currency = result.currencies[0]
        currency.rows = Array.from({ length: 20 }, (_, index) => ({
          ...currency.rows[0],
          group_id: String(index + 1),
          group_name: `Team ${index + 1}`,
        }))
        currency.group_count = currency.rows.length
        await route.fulfill({ json: result })
        return true
      },
    },
  )
})

test('unavailable CTC explains each exclusion using API counts', async () => {
  await withFixture(
    async (page) => {
      await page.goto(
        `${origin}/insights?insight=guaranteed_vs_target_ctc&year=2026&country_code=IN`,
      )
      await page.getByText('Why some employees are excluded').waitFor()
      await page
        .getByText('Without an equity status 5', { exact: true })
        .waitFor()
      await page
        .getByText('Missing a usable award allocation 3', { exact: true })
        .waitFor()
      await page
        .getByRole('link', { name: 'Review employee compensation and equity' })
        .waitFor()
      assert.equal(
        await page.getByRole('group', { name: 'Interactive chart' }).count(),
        0,
      )
    },
    {
      handle: async (route, query) => {
        const result = fixture(query)
        const currency = result.currencies[0]
        const reasons = {
          no_effective_package: 2,
          equity_unconfigured: 5,
          missing_allocation: 3,
        }
        Object.assign(currency, {
          eligible: 0,
          missing: 10,
          missing_reasons: reasons,
        })
        Object.assign(currency.rows[0], {
          eligible: 0,
          missing: 10,
          guaranteed_ctc: null,
          target_ctc: null,
          missing_reasons: reasons,
        })
        await route.fulfill({ json: result })
        return true
      },
    },
  )
})

test('touch, long labels, dark theme, and reduced motion at narrow widths', async () => {
  await withFixture(
    async (page) => {
      await page.goto(
        `${origin}/insights?insight=pay_distribution&group_by=department&country_code=IN&year=2026`,
      )
      await table(page).waitFor()
      assert.equal(
        await page.locator('html').getAttribute('data-theme'),
        'dark',
      )
      const mark = page.getByRole('button', {
        name: new RegExp(departments[1].name),
      })
      await mark.tap()
      assert.equal(await mark.getAttribute('aria-expanded'), 'true')
      assert.match(await selected(page).innerText(), /INR 90\.00/)
      await selected(page).getByRole('button', { name: 'Close details' }).tap()
      const help = page.getByRole('button', {
        name: 'About Group by',
        exact: true,
      })
      await help.tap()
      await page
        .getByRole('region', { name: 'About Group by' })
        .getByText(/Department filter limits/)
        .waitFor()
      await page.keyboard.press('Escape')
      await page.evaluate(() => scrollTo(0, 0))
      await snapshot(page, 'distribution-mobile-dark')
      await page.getByRole('combobox', { name: 'Insight view' }).tap()
      await page
        .getByRole('option', { name: 'Equity timeline', exact: true })
        .tap()
      await table(page).waitFor()
      await page.getByRole('spinbutton', { name: 'Start year' }).fill('2020')
      await page.getByRole('spinbutton', { name: 'Start year' }).press('Enter')
      await table(page)
        .getByRole('rowheader', { name: '2020 · Stock options' })
        .waitFor()
      await page.getByRole('button', { name: '2026', exact: true }).tap()
      const yearCard = selected(page)
      await yearCard.getByText('Missing allocations', { exact: true }).waitFor()
      const bounds = await yearCard.boundingBox()
      assert(bounds.x >= 0 && bounds.x + bounds.width <= 320)
      await yearCard.getByRole('button', { name: 'Close details' }).tap()
      await page.getByRole('switch', { name: 'Dark theme' }).tap()
      assert.equal(
        await page.locator('html').getAttribute('data-theme'),
        'light',
      )
      assert.equal(
        await page.evaluate(
          () => matchMedia('(prefers-reduced-motion: reduce)').matches,
        ),
        true,
      )
      for (const width of [320, 390, 768, 1024, 1440]) {
        await page.setViewportSize({ width, height: 900 })
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          true,
          `${width}px`,
        )
        if (width === 390) {
          const chart = page.locator('.insight-timeline-frame')
          const tick = await chart
            .getByText('75', { exact: true })
            .boundingBox()
          const point = await chart
            .locator('.insight-equity-point[data-series=rsu]')
            .first()
            .boundingBox()
          assert(
            Math.abs(tick.y + tick.height / 2 - point.y - point.height / 2) < 3,
            'The highest equity point aligns with the top axis tick.',
          )
          await snapshot(page, 'equity-mobile')
          await snapshot(chart, 'equity-axis-mobile')
        }
      }
    },
    {
      viewport: { width: 320, height: 880 },
      isMobile: true,
      hasTouch: true,
      colorScheme: 'dark',
      reducedMotion: 'reduce',
    },
  )
})

test(
  'live API values reconcile with every view and a package save appears on refresh',
  { skip: !liveApi },
  async () => {
    const password = process.env.PAYSCOPE_LIVE_PASSWORD
    const email = process.env.PAYSCOPE_LIVE_EMAIL
    const employeeId = process.env.PAYSCOPE_LIVE_EMPLOYEE_ID
    assert(
      password && email && /^\d+$/.test(employeeId ?? ''),
      'Provide the isolated HR credentials and fixture employee ID.',
    )
    const signIn = await fetch(`${liveApi}/api/auth/sign-in`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    assert.equal(signIn.status, 200)
    const csrf = (await signIn.json()).csrf_token
    const cookie = signIn.headers.get('set-cookie').split(';')[0]
    let report
    const page = await browser.newPage({
      viewport: { width: 1440, height: 950 },
    })
    page.setDefaultTimeout(8000)
    const errors = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.route('**/api/**', async (route) => {
      const path = new URL(route.request().url())
      const response = await fetch(`${liveApi}${path.pathname}${path.search}`, {
        headers: { cookie },
      })
      const json = await response.json()
      if (path.pathname === '/api/analytics/salary-insights' && response.ok)
        report = json
      await route.fulfill({ status: response.status, json })
    })
    const currency = 'INR'
    const year = '2026'
    const asMoney = (decimal) =>
      `${currency} ${decimal.replace(/\B(?=(\d{3})+(?!\d))(?=\d*\.)/g, ',')}`
    const first = () =>
      report.currencies.find((entry) => entry.currency_code === currency)
        .rows[0]
    let original
    let saved
    const employeePath = `${liveApi}/api/employees/${employeeId}/compensation`
    const replacePackage = (base, version) =>
      fetch(employeePath, {
        method: 'PUT',
        headers: {
          cookie,
          'X-CSRF-Token': csrf,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          annual_basic_pay: base,
          currency_code: currency,
          effective_date: original.effective_date,
          expected_version: version,
        }),
      })
    try {
      await page.goto(
        `${origin}/insights?year=${year}&country_code=IN&currency_code=${currency}`,
      )
      await table(page).waitFor()
      for (const [view, label, read, share] of [
        ['pay_distribution', 'Pay distribution', (row) => row.percentiles.p50],
        ['compensation_mix', 'Compensation mix', (row) => row.amount],
        ['country_comparison', 'Country comparison', (row) => row.spread],
        [
          'guaranteed_vs_target_ctc',
          'Guaranteed vs. target CTC',
          (row) => row.target_ctc,
        ],
        [
          'payroll_concentration',
          'Payroll concentration',
          (row) => row.payroll_share,
          true,
        ],
        ['role_bands', 'Role bands', (row) => row.percentiles.p90],
        ['equity_timeline', 'Equity timeline', (row) => row.amount],
        [
          'headcount_vs_payroll',
          'Headcount vs. payroll',
          (row) => row.headcount_share,
          true,
        ],
      ]) {
        if (view !== 'pay_distribution') {
          await Promise.all([
            nextReport(page, 'insight', view),
            page.getByRole('link', { name: label, exact: true }).click(),
          ])
        }
        await table(page).waitFor()
        assert.equal(report.insight, view)
        const value = read(first())
        assert(value != null, `The ${label} fixture needs a recorded value.`)
        const display = share ? `${value}%` : asMoney(value)
        const row = first()
        await page
          .getByRole('group', { name: 'Interactive chart' })
          .getByRole('button', { name: row.group_name ?? String(row.year) })
          .first()
          .click()
        await selected(page)
          .getByText(display, { exact: true })
          .first()
          .waitFor()
        await table(page)
          .getByRole('cell', { name: display, exact: true })
          .first()
          .waitFor()
        if (view === 'payroll_concentration')
          await snapshot(page, 'payroll-live')
        await page.keyboard.press('Escape')
      }

      await Promise.all([
        nextReport(page, 'insight', 'compensation_mix'),
        page
          .getByRole('link', { name: 'Compensation mix', exact: true })
          .click(),
      ])
      await table(page).waitFor()
      const oldAmount = first().amount
      original = await fetch(employeePath, { headers: { cookie } }).then(
        (response) => response.json(),
      )
      assert.equal(original.currency_code, currency)
      assert.equal(original.rule_version_id, null)
      assert.equal(
        original.components.length,
        0,
        'Use the isolated synthetic base-pay-only employee.',
      )
      const changed = await replacePackage(
        (Number(original.annual_basic_pay) + 50).toFixed(2),
        original.version,
      )
      assert.equal(changed.status, 200, await changed.clone().text())
      saved = await changed.json()
      await page.getByRole('button', { name: 'Refresh report' }).click()
      await table(page)
        .getByRole('cell', {
          name: asMoney((Number(oldAmount) + 50).toFixed(2)),
          exact: true,
        })
        .first()
        .waitFor()
      assert.deepEqual(errors, [])
    } finally {
      if (saved) {
        const restored = await replacePackage(
          original.annual_basic_pay,
          saved.version,
        )
        assert.equal(restored.status, 200)
      }
      await page.close()
    }
  },
)
