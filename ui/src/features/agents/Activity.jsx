import { useEffect, useState } from 'react'

const names = {
  pay_analyst: 'Pay Analyst',
  answer_writer: 'Answer Writer',
  get_report_options: 'Resolve report filters',
  get_salary_summary: 'Validate filters and calculate salary report',
}
const elapsed = (start, end) => {
  const difference = Date.parse(end) - Date.parse(start)
  return Number.isFinite(difference) ? `${(Math.max(0, difference) / 1000).toFixed(1)} s` : null
}

export default function Activity({ events = [], active = false, status }) {
  const [started] = useState(() => new Date().toISOString())
  const [now, setNow] = useState(started)
  useEffect(() => {
    if (!active) return
    const timer = setInterval(() => setNow(new Date().toISOString()), 1000)
    return () => clearInterval(timer)
  }, [active])
  if (!events.length && !active) return null
  const final = events.findLast((event) => event.type === 'final')
  const terminal = final?.payload.status || status
  const end = final?.timestamp || (active ? now : events.at(-1)?.timestamp)
  const duration = elapsed(events[0]?.timestamp || started, end || now)
  const models = events.filter((event) => event.type === 'model_completed')
  const inputTokens = models.reduce((sum, event) => sum + (event.payload.input_tokens || 0), 0)
  const outputTokens = models.reduce((sum, event) => sum + (event.payload.output_tokens || 0), 0)
  const rows = []
  for (const event of events) {
    const { type, agent_name: agent, payload } = event
    if (type === 'run_started') rows.push({ id: 'orchestrator', label: 'Workflow Orchestrator', detail: 'Started the workflow', done: true })
    if (type === 'agent_started') rows.push({ id: agent, label: names[agent] || agent, start: event.timestamp })
    if (type === 'agent_completed') {
      const row = rows.findLast((item) => item.id === agent)
      if (row) Object.assign(row, { done: true, detail: payload.outcome.replaceAll('_', ' '), duration: elapsed(row.start, event.timestamp) })
    }
    if (type === 'handoff_started') rows.push({ id: event.event_id, label: 'Workflow Orchestrator', detail: `${names[payload.source] || payload.source} → ${names[payload.target] || payload.target}`, done: true })
    if (type === 'tool_started') rows.push({ id: event.call_id || event.event_id, label: 'Report validation', detail: names[payload.tool_name] || payload.tool_name, arguments: payload.arguments, start: event.timestamp })
    if (type === 'tool_completed') {
      const row = rows.findLast((item) => item.id === event.call_id)
      if (row) Object.assign(row, { done: true, result: payload.summary, detail: `${row.detail} · ${payload.status}`, duration: `${(payload.duration_ms / 1000).toFixed(1)} s` })
    }
    if (type === 'verification_completed') rows.push({ id: event.event_id, label: 'Final verification', detail: payload.outcome === 'verified_writer' ? 'Claims checked against report evidence' : 'Used the verified report summary', done: true })
    if (type === 'model_escalated') rows.push({ id: event.event_id, label: 'Rechecking the question', detail: `${payload.from_model} → ${payload.to_model}`, done: true })
    if (type === 'tool_rejected') rows.push({ id: event.event_id, label: 'Report validation', detail: 'Invalid report request rejected', done: true })
  }
  return (
    <details className="agent-activity" key={active ? 'live' : 'saved'} open={active || undefined}>
      <summary>Report activity <span>{active ? 'In progress' : terminal?.replaceAll('_', ' ')}{duration && ` · ${duration}`}</span></summary>
      <p>Execution stages and tool results. Private reasoning is not shown.</p>
      <ol>
        {!rows.length && <li>Accepting your question…</li>}
        {rows.map((row) => (
          <li key={row.id} data-state={row.done ? 'done' : active ? 'running' : terminal}>
            <strong>{row.label}</strong>
            <span>{row.duration || (!row.done ? active ? 'Running…' : terminal?.replaceAll('_', ' ') : 'Complete')}</span>
            {row.detail && <p>{row.detail}</p>}
            {(row.arguments || row.result) && <details><summary>Tool details</summary><pre>{JSON.stringify({ filters: row.arguments, result: row.result }, null, 2)}</pre></details>}
          </li>
        ))}
      </ol>
      {models.length > 0 && <p>{models.length} model {models.length === 1 ? 'call' : 'calls'} · {inputTokens.toLocaleString()} input tokens · {outputTokens.toLocaleString()} output tokens</p>}
      {models.length > 0 && <details><summary>Model timings</summary><ul>{models.map((event) => <li key={event.event_id}>{names[event.agent_name]} · {event.payload.model} · {(event.payload.duration_ms / 1000).toFixed(1)} s{event.payload.first_update_ms != null && ` · first update ${(event.payload.first_update_ms / 1000).toFixed(1)} s`}</li>)}</ul></details>}
      {final?.run_id && <small>Run {final.run_id}</small>}
    </details>
  )
}
