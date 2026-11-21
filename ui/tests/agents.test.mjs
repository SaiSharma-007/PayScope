import assert from 'node:assert/strict'
import { test, before, after } from 'node:test'
import { setTimeout as delay } from 'node:timers/promises'
import { createServer } from 'vite'
import { chromium } from 'playwright'
import { readEvents } from '../src/features/agents/stream.js'

let server
let browser
let origin
const liveAgentApi = process.env.PAYSCOPE_TEST_AGENT_API
if (
  liveAgentApi &&
  !['127.0.0.1', 'localhost'].includes(new URL(liveAgentApi).hostname)
) {
  throw new Error('The live agent test requires a disposable API on loopback.')
}
const run = 'run-one'
const chat = 'chat-one'
const time = '2026-11-20T12:00:00Z'
const question =
  'Which Engineering role in India has the highest median base pay in INR?'
const row = {
  evidence_id: 'evidence-1',
  group_id: 3,
  group_name: 'Engineer',
  currency_code: 'INR',
  headcount: 7,
  mean: '850000.00',
  median: '900000.00',
  minimum: '600000.00',
  maximum: '930000.00',
}
const report = {
  revision: 2,
  currency_code: 'INR',
  rows: [row],
  filters: { country_code: 'IN', group_by: 'job_title', currency_code: 'INR' },
}
const summary = { id: chat, title: question, active_run_id: run }
const event = (sequence, type, payload = {}) => ({
  event_id: `event-${sequence}`,
  run_id: run,
  sequence,
  type,
  payload,
})
const sse = (events) =>
  events
    .map(
      (item) =>
        `id: ${item.sequence}\nevent: ${item.type}\ndata: ${JSON.stringify(item)}\n\n`,
    )
    .join('')

before(async () => {
  server = await createServer({
    server: {
      host: '127.0.0.1',
      port: 4177,
      strictPort: true,
      ...(liveAgentApi ? { proxy: { '/api': liveAgentApi } } : {}),
    },
  })
  await server.listen()
  origin = server.resolvedUrls.local[0]
  browser = await chromium.launch({
    executablePath: process.env.PAYSCOPE_CHROME_PATH || undefined,
  })
})

test(
  'live UI publishes a prompt and reconciles the India Engineering answer',
  {
    skip: !liveAgentApi,
    timeout: 100000,
  },
  async () => {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 900 },
    })
    try {
      const signedIn = await page.request.post(
        new URL('/api/auth/sign-in', origin).href,
        {
          data: {
            email: 'owner@example.test',
            password: 'test-agent-stream-password',
          },
        },
      )
      assert.equal(signedIn.status(), 200)
      const { csrf_token: csrf } = await signedIn.json()
      await page.goto(new URL('/admin/agent-prompts', origin).href)
      const editor = page.getByLabel('Prompt instructions')
      await editor.waitFor()
      const original = await editor.inputValue()
      assert.ok(original)
      await editor.fill(
        original + '\nAlways retain all tied groups in rankings.',
      )
      await page.getByRole('button', { name: 'Save draft' }).click()
      await page.getByRole('button', { name: 'Review draft' }).click()
      await page.getByRole('button', { name: 'Publish new version' }).click()
      await page.getByText('Published v2.', { exact: true }).waitFor()
      await page.goto(new URL('/insights/ask', origin).href)
      await page.getByRole('button', { name: question }).click()
      await page.getByRole('button', { name: 'Ask', exact: true }).click()
      const go = page.getByRole('link', { name: 'Open report' })
      await page.waitForURL(/\?chat=/)
      const id = new URL(page.url()).searchParams.get('chat')
      let outcome
      for (let attempt = 0; attempt < 135; attempt++) {
        const response = await page.request.get(
          new URL(`/api/agent/conversations/${id}`, origin).href,
        )
        assert.equal(response.status(), 200)
        outcome = (await response.json()).turns.at(-1)
        if (outcome && !['queued', 'running'].includes(outcome.status)) break
        await delay(500)
      }
      assert.equal(
        outcome?.status,
        'completed',
        outcome?.messages.at(-1)?.structured_content?.error?.code,
      )
      await page
        .getByText('Engineer', { exact: false })
        .and(page.locator('.agent-message.assistant p'))
        .waitFor()
      await go.click()
      await page
        .getByRole('rowheader', { name: 'Engineer', exact: true })
        .waitFor()
      const originalReport = page.url()
      const update = await page.request.put(
        new URL('/api/employees/1/salary', origin).href,
        {
          headers: { 'X-CSRF-Token': csrf },
          data: { annual_gross_base: '101.00', currency_code: 'INR' },
        },
      )
      assert.equal(update.status(), 200)
      await page.reload()
      await page
        .getByText('Salary data has changed since this answer.', {
          exact: false,
        })
        .waitFor()
      assert.equal(page.url(), originalReport)
      await page.getByRole('link', { name: 'Back to Ask about pay' }).click()
      await page
        .getByText('Engineer', { exact: false })
        .and(page.locator('.agent-message.assistant p'))
        .waitFor()
    } finally {
      await page.close()
    }
  },
)
after(async () => {
  await browser?.close()
  await server?.close()
})

function session(admin) {
  return {
    user: { id: 'hr', display_name: 'HR Manager', manage_agent_prompts: admin },
    csrf_token: 'fixture',
    expires_at: new Date(Date.now() + 3_600_000).toISOString(),
  }
}

test('SSE reader handles fragmented UTF-8, comments, and CRLF', async () => {
  const source = new TextEncoder().encode(
    ': heartbeat\r\n\r\ndata: {"text":"₹"}\r\n\r\n',
  )
  const body = new ReadableStream({
    start(controller) {
      for (const byte of source) controller.enqueue(Uint8Array.of(byte))
      controller.close()
    },
  })
  const events = []
  for await (const value of readEvents(body)) events.push(value)
  assert.deepEqual(events, [{ text: '₹' }])
})

test('workforce charts retain zero-count countries and open a currency-free report', async () => {
  const page = await browser.newPage({ viewport: { width: 1200, height: 900 } })
  const counts = { report_type: 'workforce_headcount', metric: 'headcount', operation: 'lowest', revision: 4, filters: { group_by: 'country' }, rows: [
    { evidence_id: 'in', group_id: 'IN', group_name: 'India', headcount: 12, currency_code: '' },
    { evidence_id: 'de', group_id: 'DE', group_name: 'Germany', headcount: 0, currency_code: '' },
  ] }
  await page.route('**/api/**', (route) => {
    const url = new URL(route.request().url())
    const send = (json) => route.fulfill({ json })
    if (url.pathname.endsWith('/auth/session')) return send(session(false))
    if (url.pathname.endsWith('/conversations')) return send({ items: [{ ...summary, active_run_id: null }] })
    if (url.pathname.endsWith(`/conversations/${chat}`)) return send({ ...summary, active_run_id: null, turns: [{ run_id: run, status: 'completed', messages: [{ role: 'assistant', text: 'Germany — lowest headcount: 0 employees.', structured_content: { report: counts } }] }] })
    if (url.pathname.endsWith('/analytics/headcount')) {
      assert.equal(url.searchParams.has('currency_code'), false)
      return send(counts)
    }
    return route.fulfill({ status: 404 })
  })
  try {
    await page.goto(new URL(`/insights/ask?chat=${chat}`, origin).href)
    await page.getByText('Germany — lowest headcount: 0 employees.', { exact: true }).waitFor()
    assert.equal(await page.locator('.insight-mark-label').first().innerText(), 'Germany')
    assert.equal(await page.locator('.insight-mark').count(), 2)
    await page.getByRole('link', { name: 'Open report', exact: true }).click()
    await page.getByRole('heading', { name: 'Workforce headcount', exact: true }).waitFor()
    await page.locator('.insight-mark').first().waitFor()
    assert.equal(await page.getByRole('columnheader', { name: 'Currency', exact: true }).count(), 0)
    assert.equal(await page.getByRole('columnheader', { name: 'Average', exact: true }).count(), 0)
  } finally { await page.close() }
})

test('new chat keeps its POST stream and restores all five activity stages', async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  let detailReads = 0
  let submissions = 0
  const prompt = 'What is the average annual base pay in Germany in EUR?'
  const answer = 'Germany — average annual gross base pay of EUR 75,000.00.'
  const trace = [
    event(1, 'accepted', { conversation_id: chat }),
    event(2, 'run_started'),
    { ...event(3, 'agent_started'), agent_name: 'pay_analyst' },
    { ...event(4, 'tool_started', { tool_name: 'get_salary_summary', arguments: { country_code: 'DE', currency_code: 'EUR' } }), call_id: 'salary-tool' },
    { ...event(5, 'tool_completed', { status: 'completed', duration_ms: 120, summary: { row_count: 1, cache_status: 'hit' } }), call_id: 'salary-tool' },
    { ...event(6, 'agent_completed', { outcome: 'report_ready' }), agent_name: 'pay_analyst' },
    event(7, 'handoff_started', { source: 'pay_analyst', target: 'answer_writer' }),
    { ...event(8, 'agent_started'), agent_name: 'answer_writer' },
    { ...event(9, 'model_completed', { model: 'fixture-model', duration_ms: 500, first_update_ms: 100, input_tokens: 100, output_tokens: 20 }), agent_name: 'answer_writer' },
    event(10, 'verification_completed', { outcome: 'verified_writer' }),
    { ...event(11, 'agent_completed', { outcome: 'verified_writer' }), agent_name: 'answer_writer' },
    event(12, 'final', { status: 'completed', answer }),
  ].map((item, index) => ({ ...item, timestamp: new Date(Date.parse(time) + index * 100).toISOString() }))
  await page.route('**/api/**', (route) => {
    const path = new URL(route.request().url()).pathname
    const send = (json) => route.fulfill({ json })
    if (path.endsWith('/auth/session')) return send(session(false))
    if (path.endsWith('/conversations')) return send({ items: submissions ? [{ ...summary, title: prompt, active_run_id: null }] : [] })
    if (path.endsWith(`/conversations/${chat}`)) {
      detailReads++
      return send({ ...summary, title: prompt, active_run_id: null, turns: [{ run_id: run, status: 'completed', events: trace, messages: [{ role: 'user', text: prompt }, { role: 'assistant', text: answer }] }] })
    }
    if (path.endsWith('/runs')) {
      submissions++
      return route.fulfill({ contentType: 'text/event-stream', body: sse(trace) })
    }
    throw new Error(`Unexpected request: ${path}`)
  })
  try {
    await page.goto(new URL('/insights/ask', origin).href)
    await page.getByLabel('Your pay question').fill(prompt)
    await page.getByLabel('Your pay question').press('Enter')
    await page.getByText(answer, { exact: true }).waitFor()
    assert.equal(submissions, 1)
    assert.equal(detailReads, 0, 'Adopting the chat ID must not reload the thread')
    await page.reload()
    await page.getByText(answer, { exact: true }).waitFor()
    await page.getByText('Report activity', { exact: false }).click()
    for (const label of ['Pay Analyst', 'Report validation', 'Answer Writer', 'Final verification']) {
      assert.equal(await page.getByText(label, { exact: true }).isVisible(), true)
    }
    assert.equal(await page.getByText('Workflow Orchestrator', { exact: true }).count(), 2)
    await page.getByText('1 model call', { exact: false }).waitFor()
    await page.screenshot({ path: '../artifacts/verification/agent-chat-desktop.png' })
    await page.setViewportSize({ width: 390, height: 844 })
    const box = await page.getByLabel('Your pay question').boundingBox()
    assert.ok(box.y >= 0 && box.y + box.height <= 844, 'Composer stays visible on mobile')
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    await page.screenshot({ path: '../artifacts/verification/agent-chat-mobile.png' })
  } finally {
    await page.close()
  }
})

test('HR reconnects from a saved chat cursor and verifies the report revision', async () => {
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    reducedMotion: 'reduce',
  })
  let submissions = 0
  let replays = 0
  let stopped = false
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const send = (json) => route.fulfill({ json })
    const stream = (events) =>
      route.fulfill({ contentType: 'text/event-stream', body: sse(events) })
    const path = url.pathname
    if (path.endsWith('/auth/session')) return send(session(false))
    if (path.endsWith('/conversations'))
      return send({ items: submissions ? [summary] : [], next_offset: null })
    if (path.endsWith(`/conversations/${chat}`))
      return send({
        ...summary,
        active_run_id: stopped ? null : run,
        next_before_turn: null,
        turns: [
          {
            run_id: run,
            status: stopped ? 'completed' : 'running',
            messages: [
              { role: 'user', text: question },
              ...(stopped
                ? [
                    {
                      role: 'assistant',
                      text: 'Engineer has the highest median.',
                      structured_content: { report },
                    },
                  ]
                : []),
            ],
          },
        ],
      })
    if (path.endsWith('/runs')) {
      assert.equal(route.request().postDataJSON().question, question)
      assert.equal(route.request().headers()['x-csrf-token'], 'fixture')
      assert.ok(route.request().headers()['idempotency-key'])
      submissions++
      return stream([event(1, 'accepted', { conversation_id: chat }), event(2, 'token', { text: 'Engineer' }), event(2, 'token', { text: 'duplicate' })])
    }
    if (path.endsWith('/events')) {
      replays++
      assert.equal(url.searchParams.get('after'), '2')
      stopped = true
      return stream([
        event(2, 'token', { text: 'duplicate' }),
        event(3, 'final', {
          status: 'completed',
          answer: 'Engineer has the highest median.',
          report,
        }),
      ])
    }
    if (path.endsWith('/salary-summary')) {
      assert.equal(url.searchParams.get('country_code'), 'IN')
      assert.equal(url.searchParams.get('currency_code'), 'INR')
      assert.equal(url.searchParams.get('group_by'), 'job_title')
      return send({ revision: 3, rows: [row] })
    }
    return route.fulfill({ status: 404 })
  })
  try {
    await page.goto(new URL('/insights/ask', origin).href)
    await page.getByRole('button', { name: question }).click()
    await page.getByRole('button', { name: 'Ask', exact: true }).click()
    await page.getByText('Connection interrupted.').waitFor()
    assert.equal(await page.getByText('duplicate').count(), 0)
    await page.getByRole('button', { name: 'Reconnect' }).click()
    await page.getByText('Engineer has the highest median.').waitFor()
    assert.equal(submissions, 1)
    assert.equal(replays, 1)
    await page.reload()
    await page.getByRole('link', { name: 'Open report' }).click()
    await page
      .getByText('Salary data has changed since this answer.', { exact: false })
      .waitFor()
    await page.getByRole('link', { name: 'Back to Ask about pay' }).click()
    await page.getByText('Engineer has the highest median.').waitFor()
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
      true,
    )
    await page.goto(new URL('/admin/agent-prompts', origin).href)
    await page.getByText('Prompt access is restricted').waitFor()
    assert.equal(
      await page
        .getByRole('navigation')
        .getByRole('link', { name: 'Agent prompts' })
        .count(),
      0,
    )
  } finally {
    await page.close()
  }
})

test('cached chats preserve drafts, interactive figures, and delete with Undo', async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const other = { id: 'chat-two', title: 'Country comparison', active_run_id: null }
  const first = { ...summary, title: 'Engineering salaries', active_run_id: null }
  const counts = new Map()
  let removed = false
  let rejectDelete = true
  const figures = { ...report, rows: [row, { ...row, evidence_id: 'evidence-2', group_id: 4, group_name: 'Designer', mean: '400000.00', median: '500000.00', minimum: '300000.00', maximum: '700000.00', headcount: 4 }] }
  await page.route('**/api/**', (route) => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    const send = (json) => route.fulfill({ json })
    if (path.endsWith('/auth/session')) return send(session(false))
    if (path.endsWith('/conversations')) return send({ items: removed ? [other] : [first, other], next_offset: null })
    if (path.endsWith(`/${chat}/restore`)) {
      assert.equal(req.headers()['x-csrf-token'], 'fixture')
      removed = false
      return route.fulfill({ status: 204 })
    }
    if (path.endsWith(`/conversations/${chat}`) && req.method() === 'DELETE') {
      assert.equal(req.headers()['x-csrf-token'], 'fixture')
      if (rejectDelete) {
        rejectDelete = false
        return route.fulfill({ status: 409, json: { detail: { message: 'Stop the active response before deleting this chat.' } } })
      }
      removed = true
      return route.fulfill({ status: 204 })
    }
    const selected = [first, other].find((item) => path.endsWith(`/conversations/${item.id}`))
    if (selected) {
      counts.set(selected.id, (counts.get(selected.id) || 0) + 1)
      return send({ ...selected, next_before_turn: null, turns: [{ run_id: selected.id + '-run', status: 'completed', messages: [
        { role: 'user', text: selected.title },
        { role: 'assistant', text: selected.id === chat ? 'Engineering salary comparison.' : 'Country salary comparison.', structured_content: selected.id === chat ? { report: figures } : {} },
      ] }] })
    }
    return route.fulfill({ status: 404 })
  })
  try {
    await page.goto(new URL(`/insights/ask?chat=${chat}`, origin).href)
    await page.getByText('Engineering salary comparison.', { exact: true }).waitFor()
    await page.getByLabel('Your pay question').fill('Keep this draft')
    await page.getByRole('link', { name: other.title, exact: true }).click()
    await page.getByText('Country salary comparison.', { exact: true }).waitFor()
    await page.getByRole('link', { name: first.title, exact: true }).click()
    await page.getByText('Engineering salary comparison.', { exact: true }).waitFor()
    assert.equal(await page.getByLabel('Your pay question').inputValue(), 'Keep this draft')
    assert.equal(counts.get(chat), 1)
    assert.equal(counts.get(other.id), 1)
    const graph = page.getByRole('region', { name: 'Interactive salary report' })
    await graph.getByRole('combobox', { name: 'Chart measure' }).click()
    await page.getByRole('option', { name: 'Median base pay', exact: true }).click()
    await graph.getByRole('combobox', { name: 'Chart order' }).click()
    await page.getByRole('option', { name: 'Lowest first', exact: true }).click()
    assert.equal(await graph.locator('.insight-mark-label').first().innerText(), 'Designer')
    await graph.locator('.insight-mark').first().click()
    await page.getByRole('region', { name: 'Selected values' }).getByText('Designer', { exact: true }).waitFor()
    await page.keyboard.press('Escape')
    await page.screenshot({ path: '../artifacts/verification/chat-interactive-report.png' })
    await page.setViewportSize({ width: 390, height: 844 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    await page.screenshot({ path: '../artifacts/verification/chat-interactive-report-mobile.png' })
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.getByRole('button', { name: `Delete chat: ${first.title}` }).click()
    await page.getByRole('alert').filter({ hasText: 'Stop the active response before deleting this chat.' }).waitFor()
    assert.equal(await page.getByRole('link', { name: first.title, exact: true }).count(), 1)
    await page.getByRole('button', { name: `Delete chat: ${first.title}` }).click()
    await page.getByRole('button', { name: 'Undo', exact: true }).waitFor()
    assert.equal(await page.getByRole('link', { name: first.title, exact: true }).count(), 0)
    await page.getByText('Engineering salary comparison.', { exact: true }).waitFor({ state: 'hidden' })
    await page.getByRole('button', { name: 'Undo', exact: true }).click()
    await page.getByRole('link', { name: first.title, exact: true }).click()
    await page.getByText('Engineering salary comparison.', { exact: true }).waitFor()
    assert.equal(counts.get(chat), 2, 'Deleted chat snapshots are evicted from memory')
  } finally {
    await page.close()
  }
})

test('admin reviews, publishes, restores, and keeps edits after a version conflict', async () => {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    colorScheme: 'dark',
  })
  const versions = [
    {
      version: 1,
      author_name: null,
      published_at: time,
      change_note: 'Initial',
      body: 'Original instructions',
    },
  ]
  let revision = 0
  let draft = null
  let rejectSave = true
  const detail = () => ({ active: versions[0], draft, edit_revision: revision })
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const send = (json) => route.fulfill({ json })
    const req = route.request()
    if (path.endsWith('/auth/session')) return send(session(true))
    if (path.endsWith('/pay_analyst')) return send(detail())
    if (path.endsWith('/versions'))
      return send({ items: versions, next_before_version: null })
    if (/\/versions\/\d+$/.test(path))
      return send(
        versions.find(
          (version) => version.version === Number(path.split('/').at(-1)),
        ),
      )
    const input = req.postDataJSON()
    assert.equal(req.headers()['x-csrf-token'], 'fixture')
    assert.equal(input.expected_revision, revision)
    revision++
    if (path.endsWith('/draft') && rejectSave) {
      rejectSave = false
      return route.fulfill({
        status: 409,
        json: {
          detail: { code: 'PROMPT_CHANGED', message: 'This prompt changed.' },
        },
      })
    }
    if (path.endsWith('/draft'))
      draft = { body: input.body, change_note: input.change_note }
    else if (path.endsWith('/restore'))
      draft = {
        body: versions.find((version) => version.version === input.version)
          .body,
        change_note: 'Restored from v1',
      }
    else if (path.endsWith('/publish')) {
      versions.unshift({
        ...draft,
        version: 2,
        author_name: 'HR Manager',
        published_at: time,
      })
      draft = null
    }
    return send(detail())
  })
  try {
    await page.goto(new URL('/admin/agent-prompts', origin).href)
    const editor = page.getByLabel('Prompt instructions')
    await editor.fill('Revised instructions')
    await page.getByRole('button', { name: 'Save draft' }).click()
    await page
      .getByRole('button', { name: 'Load latest version and keep my edits' })
      .click()
    assert.equal(await editor.inputValue(), 'Revised instructions')
    await page.getByRole('button', { name: 'Save draft' }).click()
    await page.getByRole('button', { name: 'Review draft' }).click()
    await page
      .getByRole('region', { name: 'Review before publishing' })
      .getByText('Original instructions')
      .waitFor()
    await page.getByRole('button', { name: 'Publish new version' }).click()
    await page.getByText('Published v2.', { exact: true }).waitFor()
    await page.getByRole('button', { name: /^v1/ }).click()
    await page.getByRole('button', { name: 'Copy to draft' }).click()
    await page.getByText('Copied the previous version to a draft.').waitFor()
    assert.equal(await editor.inputValue(), 'Original instructions')
  } finally {
    await page.close()
  }
})

test('Stop, a linked retry, and clarification stay in their own chat', async () => {
  const page = await browser.newPage({ viewport: { width: 1024, height: 820 } })
  const other = {
    id: 'chat-two',
    title: 'Another conversation',
    active_run_id: null,
  }
  let stopped = false
  const stream = (route, events) =>
    route.fulfill({ contentType: 'text/event-stream', body: sse(events) })
  await page.route('**/api/**', (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname
    const send = (json) => route.fulfill({ json })
    if (path.endsWith('/auth/session')) return send(session(false))
    if (path.endsWith('/conversations'))
      return send({ items: [summary, other] })
    if (path.endsWith(`/conversations/${chat}`))
      return send({
        ...summary,
        turns: [
          {
            run_id: run,
            status: 'running',
            messages: [{ role: 'user', text: question }],
          },
        ],
      })
    if (path.endsWith(`/conversations/${other.id}`))
      return send({ ...other, turns: [] })
    if (path.endsWith('/cancel')) {
      stopped = true
      return send({ status: 'running', cancel_requested: true })
    }
    if (path.endsWith('/events'))
      return stream(
        route,
        stopped
          ? [
              event(2, 'final', {
                status: 'cancelled',
                answer: null,
                is_partial: true,
              }),
            ]
          : [event(1, 'accepted', { conversation_id: chat })],
      )
    if (path.endsWith('/runs')) {
      const input = req.postDataJSON()
      if (input.kind === 'retry') {
        assert.equal(input.parent_run_id, run)
        assert.equal(input.question, question)
        return stream(route, [
          {
            ...event(1, 'accepted', { conversation_id: chat }),
            run_id: 'retry-run',
          },
          {
            ...event(2, 'final', {
              status: 'awaiting_clarification',
              answer: 'Which currency should I use?',
              clarification: { field: 'currency', choices: ['INR', 'USD'] },
            }),
            run_id: 'retry-run',
          },
        ])
      }
      assert.equal(input.kind, 'clarification')
      assert.equal(input.parent_run_id, 'retry-run')
      assert.equal(input.question, 'INR')
      return stream(route, [
        {
          ...event(1, 'accepted', { conversation_id: chat }),
          run_id: 'clarified-run',
        },
        {
          ...event(2, 'final', {
            status: 'failed',
            answer: 'The model could not finish the request.',
          }),
          run_id: 'clarified-run',
        },
      ])
    }
    return route.fulfill({ status: 404 })
  })
  try {
    await page.goto(new URL(`/insights/ask?chat=${chat}`, origin).href)
    await page.getByText('Connection interrupted.').waitFor()
    const stop = page.getByRole('button', { name: 'Stop' })
    await stop.focus()
    await page.keyboard.press('Enter')
    await page.getByRole('button', { name: 'Retry question' }).click()
    await page.getByText('Which currency should I use?').waitFor()
    await page.getByRole('button', { name: 'INR', exact: true }).click()
    await page.getByText('The model could not finish the request.').waitFor()
    await page.getByRole('link', { name: 'Another conversation' }).click()
    await page
      .getByRole('link', { name: 'Another conversation' })
      .and(page.locator('[aria-current="page"]'))
      .waitFor()
    assert.equal(
      await page.getByText('The model could not finish the request.').count(),
      0,
    )
  } finally {
    await page.close()
  }
})
