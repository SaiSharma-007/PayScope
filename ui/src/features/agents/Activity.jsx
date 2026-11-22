import { Check, Circle, CircleAlert, LoaderCircle } from 'lucide-react'
import { Trace, TraceCollapsible, TraceCollapsibleContent, TraceCollapsibleTrigger, TraceDescription, TraceIcon, TraceLine, TraceTitle } from '../../components/ui/trace'
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

export default function Activity({ events = [], active = false, status, diagnostics = false }) {
  const [openChoice, setOpenChoice] = useState(null)
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
      if (row) Object.assign(row, { done: true, detail: payload.outcome?.replaceAll('_', ' '), duration: elapsed(row.start, event.timestamp) })
    }
    if (type === 'handoff_started') rows.push({ id: event.event_id, label: 'Workflow Orchestrator', detail: `${names[payload.source] || payload.source} → ${names[payload.target] || payload.target}`, done: true })
    if (type === 'tool_started') rows.push({ id: event.call_id || event.event_id, label: 'Report validation', detail: names[payload.tool_name] || payload.tool_name, arguments: payload.arguments, start: event.timestamp })
    if (type === 'tool_completed') {
      const row = rows.findLast((item) => item.id === event.call_id)
      if (row) Object.assign(row, { done: true, result: payload.summary, detail: row.detail, failed: payload.status === 'failed' || payload.status === 'error', duration: `${(payload.duration_ms / 1000).toFixed(1)} s` })
    }
    if (type === 'verification_completed') rows.push({ id: event.event_id, label: 'Final verification', detail: payload.outcome === 'verified_writer' ? 'Claims checked against report evidence' : 'Used the verified report summary', done: true })
    if (type === 'model_escalated') rows.push({ id: event.event_id, label: 'Rechecking the question', detail: diagnostics ? `${payload.from_model} → ${payload.to_model}` : undefined, done: true })
    if (type === 'tool_rejected') rows.push({ id: event.event_id, label: 'Report validation', detail: 'Invalid report request rejected', done: true })
  }
  const runningRow = active ? rows.findLast((row) => !row.done) : null
  const statusLabel = active ? 'In progress' : terminal === 'disconnected'
    ? 'Interrupted'
    : terminal === 'cancelled'
      ? 'Stopped'
      : terminal?.replaceAll('_', ' ')
  const summaryStatus = statusLabel && statusLabel[0].toUpperCase() + statusLabel.slice(1)
  return (
    <TraceCollapsible className="agent-live-trace" open={openChoice ?? active} onOpenChange={setOpenChoice}>
      <TraceCollapsibleTrigger>
        <strong>Report activity</strong>
        <span>{summaryStatus}{rows.length > 0 && ` · ${rows.length} ${rows.length === 1 ? 'step' : 'steps'}`}{duration && ` · ${duration}`}</span>
      </TraceCollapsibleTrigger>
      <TraceCollapsibleContent>
        <Trace role="list" aria-label="Report steps">
          {!rows.length && <TraceLine role="listitem" status="running"><TraceTitle>Waiting for the run to start</TraceTitle></TraceLine>}
          {rows.map((row, index) => {
            const state = row.failed || (!row.done && !active) ? 'error'
              : row.done ? 'done' : row === runningRow ? 'running' : 'pending'
            const Icon = { done: Check, running: LoaderCircle, error: CircleAlert, pending: Circle }[state]
            return (
              <div className="agent-trace-step" role="listitem" key={`${row.id}:${index}`}>
                <TraceLine status={state}>
                  <TraceIcon><Icon /></TraceIcon>
                  <TraceTitle>{row.label}</TraceTitle>
                  <TraceDescription>{state === 'running' ? 'Running' : state === 'error'
                    ? row.failed ? 'Failed' : 'Interrupted'
                    : row.duration || (row.done ? 'Complete' : 'In progress')}</TraceDescription>
                </TraceLine>
                {row.detail && <p>{row.detail}</p>}
                {diagnostics && (row.arguments || row.result) && <details><summary>Tool details</summary><pre>{JSON.stringify({ filters: row.arguments, result: row.result }, null, 2)}</pre></details>}
              </div>
            )
          })}
        </Trace>
        {models.length > 0 && <p className="agent-trace-meta">{models.length} model {models.length === 1 ? 'call' : 'calls'}{diagnostics && ` · ${inputTokens.toLocaleString()} input tokens · ${outputTokens.toLocaleString()} output tokens`}</p>}
        {diagnostics && models.length > 0 && <details><summary>Model timings</summary><ul>{models.map((event) => <li key={event.event_id}>{names[event.agent_name]} · {event.payload.model} · {(event.payload.duration_ms / 1000).toFixed(1)} s{event.payload.first_update_ms != null && ` · first update ${(event.payload.first_update_ms / 1000).toFixed(1)} s`}</li>)}</ul></details>}
        {final?.run_id && <small className="agent-trace-meta">Run {final.run_id}</small>}
      </TraceCollapsibleContent>
    </TraceCollapsible>
  )
}
