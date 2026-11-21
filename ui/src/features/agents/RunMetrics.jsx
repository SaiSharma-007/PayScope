import { useState } from 'react'

const number = value => value == null ? '—' : Number(value).toLocaleString()
const amount = row => Number(row.input_tokens || 0) + Number(row.output_tokens || 0)
const date = value => new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(new Date(value))

export default function RunMetrics({ usage, statuses = [], statusNames }) {
  const [selected, setSelected] = useState(null)
  const totalRuns = statuses.reduce((sum, row) => sum + row.count, 0)
  const totals = usage?.totals
  const daily = usage?.daily || []
  const selectedDay = daily.find(row => row.day === selected) || daily.at(-1)
  const max = Math.max(1, ...daily.map(amount))
  return (
    <section className="run-metrics" aria-label="Run and token metrics">
      <dl className="run-metric-totals">
        <div><dt>Matching runs</dt><dd>{number(totalRuns)}</dd></div>
        <div><dt>Model responses</dt><dd>{number(totals?.calls)}</dd></div>
        <div><dt>Reported input tokens</dt><dd>{number(totals?.input_tokens)}</dd></div>
        <div><dt>Reported output tokens</dt><dd>{number(totals?.output_tokens)}</dd></div>
      </dl>
      <div className="run-metric-charts">
        <section className="agent-panel run-metric-panel">
          <h2>Token usage by day</h2>
          <p>Latest {daily.length || 14} active days in the filtered results · UTC</p>
          {totals?.calls > 0 && <p>{number(totals.complete_calls)} of {number(totals.calls)} model responses reported both token counts.</p>}
          {daily.some(row => row.input_tokens != null || row.output_tokens != null) ? <>
            <div className="token-legend"><span>Input tokens</span><span>Output tokens</span></div>
            <div className="token-bars" role="group" aria-label="Select a day for exact token usage">
              {daily.map(row => <button key={row.day} type="button" aria-pressed={selectedDay?.day === row.day}
                onClick={() => setSelected(row.day)} aria-label={`${date(row.day)}: ${number(row.input_tokens)} input, ${number(row.output_tokens)} output`}>
                <span className="token-bar" aria-hidden="true">
                  <i className="token-output" style={{ height: `${Number(row.output_tokens || 0) / max * 100}%` }} />
                  <i className="token-input" style={{ height: `${Number(row.input_tokens || 0) / max * 100}%` }} />
                </span>
              </button>)}
            </div>
            <div className="token-axis"><span>{date(daily[0].day)}</span><span>{date(daily.at(-1).day)}</span></div>
            <p className="token-reading" aria-live="polite"><strong>{date(selectedDay.day)}</strong> · {number(selectedDay.input_tokens)} input · {number(selectedDay.output_tokens)} output</p>
          </> : <p className="token-reading">No token counts reported for these runs.</p>}
        </section>
        <section className="agent-panel run-metric-panel">
          <h2>Run outcomes</h2>
          <p>Distribution across all matching runs</p>
          {!totalRuns && <p className="token-reading">No matching runs.</p>}
          <ul className="run-outcomes">
            {[...statuses].sort((a, b) => b.count - a.count || a.status.localeCompare(b.status)).map(row => (
              <li key={row.status}><span>{statusNames[row.status] || row.status}</span><strong>{number(row.count)}</strong>
                <meter min="0" max={totalRuns} value={row.count} aria-label={`${statusNames[row.status] || row.status} runs`} />
                {row.duration_samples > 0 && <small>{Number(row.average_seconds).toFixed(1)} s average · {number(row.duration_samples)} timed</small>}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </section>
  )
}
