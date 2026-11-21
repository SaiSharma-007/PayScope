import { useEffect, useState } from 'react'
import { ArrowUpRight, FileChartColumn, Trash2 } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useDeleteConfirmation } from '../../components/useDeleteConfirmation'
import { markSaved } from './savedState'
import { request } from '../../lib/http'
import { useAuth } from '../auth/useAuth'
import ReportChart from './ReportChart'
import SelectField from '../../components/SelectField'
import './agents.css'
import './agent-polish.css'

export default function SavedReports() {
  const { confirm, confirmation } = useDeleteConfirmation()
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const query = params.toString()
  const [search, setSearch] = useState(params.get('q') || '')
  const [type, setType] = useState(params.get('report_type') || '')
  const [result, setResult] = useState(null)
  const [revision, setRevision] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [deleted, setDeleted] = useState(null)
  const { session, expire, sessionCache } = useAuth()
  const key = id || query
  useEffect(() => {
    if (id && deleted === id) return
    const controller = new AbortController()
    request(id ? `/saved-reports/${id}` : `/saved-reports?${query}`, { signal: controller.signal }).then((data) => { setResult({ key, data }); setError('') }).catch((problem) => { if (problem.name !== 'AbortError') { if (problem.status === 401) expire(); setError(problem.message) } })
    return () => controller.abort()
  }, [id, query, key, revision, expire, deleted])
  const data = result?.key === key ? result.data : null
  async function mutate(path, method, body) {
    setBusy(true); setError('')
    try { await request(path, { method, csrf: session.csrf_token, ...(body ? { body: JSON.stringify(body) } : {}) }); if (method === 'DELETE') { const source = id ? data : data?.items.find((item) => path.endsWith(item.id)); if (source) markSaved(sessionCache, source.source_run_id, null) }; setRevision((value) => value + 1); return true }
    catch (problem) { if (problem.status === 401) expire(); setError(problem.message); return false }
    finally { setBusy(false) }
  }
  function confirmReport(report) {
    confirm({ kind: 'report', title: 'Delete this saved report?', name: report.title, description: 'This snapshot will be removed from your saved-report library.', note: 'The original chat is unaffected. You can undo this deletion.', actionLabel: 'Delete report' }, async () => {
      if (!await mutate(`/saved-reports/${report.id}`, 'DELETE')) return false
      setDeleted(report.id)
    })
  }
  return <main id="main" className="page agent-page saved-reports-page">
    {confirmation}
    <header className="agent-heading"><div><h1>Saved reports</h1><p>Independent snapshots of your verified reports.</p></div><Link className="button secondary" to="/insights/ask">Ask about pay <ArrowUpRight size={16} aria-hidden="true" /></Link></header>
    {error && <p role="alert">{error}</p>}
    {deleted && <p role="status">Report deleted. <button className="button secondary" disabled={busy} onClick={async () => { if (await mutate(`/saved-reports/${deleted}/restore`, 'POST')) setDeleted(null) }}>Undo</button></p>}
    {!id && <form className="saved-reports-filters" noValidate onSubmit={(event) => { event.preventDefault(); setParams({ q: search, report_type: type }) }}>
      <label>Search reports<input name="q" type="search" placeholder="Find a saved report…" value={search} onChange={(event) => setSearch(event.target.value)} /></label>{search && <button className="button secondary" type="button" onClick={() => { setSearch(''); setParams({ report_type: type }) }}>Clear search</button>}
      <SelectField id="saved-report-type" label="Report type" value={type} placeholder="All types" options={[{ value: 'annual_gross_base', label: 'Annual base pay' }, { value: 'workforce_headcount', label: 'Workforce headcount' }]} onChange={(value) => { setType(value); setParams({ q: search, report_type: value }) }} />
      <button className="button secondary">Search</button>
    </form>}
    {id && deleted === id ? <Link to="/saved-reports">Back to saved reports</Link> : !data ? error ? <button className="button secondary" onClick={() => setRevision((value) => value + 1)}>Retry</button> : <p role="status">Loading reports…</p> : id ? <article className="agent-panel saved-report-detail">
      <Link to="/saved-reports">Back to saved reports</Link>
      <h2>{data.title}</h2><p>{data.description}</p><p>{data.summary}</p>
      <p className="saved-report-timestamps">Generated {new Date(data.generated_at).toLocaleString()} · saved {new Date(data.saved_at).toLocaleString()}</p>
      <ReportChart report={{ ...data.report, chart_view: data.chart_view }} />
      <details><summary>Exact saved values</summary><div className="agent-table-scroll"><table><thead><tr><th>Group</th><th>Employees</th>{data.report.report_type !== 'workforce_headcount' && <><th>Currency</th><th>Average</th><th>Median</th><th>Minimum</th><th>Maximum</th></>}</tr></thead><tbody>{data.report.rows.map((row) => <tr key={row.evidence_id}><th>{row.group_name || 'All matching employees'}</th><td>{row.headcount}</td>{data.report.report_type !== 'workforce_headcount' && <><td>{row.currency_code}</td><td>{row.mean}</td><td>{row.median}</td><td>{row.minimum}</td><td>{row.maximum}</td></>}</tr>)}</tbody></table></div></details>
      <div className="saved-report-links">{data.source_available ? <Link to={`/insights/ask?chat=${data.source_conversation_id}`}>Original chat</Link> : <p>Original chat deleted</p>}
      <Link to={`/insights/base-pay?${new URLSearchParams({ ...data.report.filters, revision: data.report.revision, report_type: data.report.report_type })}`}>Open current report <ArrowUpRight size={14} aria-hidden="true" /></Link></div>
      <details><summary>Edit title and description</summary><form key={data.id + data.title + data.description} noValidate onSubmit={async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); await mutate(`/saved-reports/${id}`, 'PATCH', { title: form.get('title'), description: form.get('description') }) }}>
        <label>Title<input name="title" defaultValue={data.title} maxLength={160} /></label><label>Description<textarea name="description" className="resize-none" defaultValue={data.description} maxLength={2000} /></label><button className="button secondary" disabled={busy}>Save details</button>
      </form></details>
      <button className="button secondary" disabled={busy} onClick={() => confirmReport(data)}>Delete report</button>
    </article> : <section className="saved-report-grid" aria-label="Saved report library">
      {!data.items.length && <p>No saved reports. Save a report from a completed chat response.</p>}
      {data.items.map((item) => <article className="agent-panel saved-report-card" key={item.id}><div className="saved-report-card-icon"><FileChartColumn size={21} aria-hidden="true" /></div><h2><Link to={`/saved-reports/${item.id}`}>{item.title}</Link></h2><p>{item.description}</p><p className="saved-report-summary">{item.summary}</p><footer className="saved-report-card-footer"><small>{item.report.report_type === 'workforce_headcount' ? 'Workforce headcount' : 'Annual base pay'} · {new Date(item.saved_at).toLocaleDateString()}</small><button className="button secondary" disabled={busy} onClick={() => confirmReport(item)} title="Delete report"><Trash2 size={16} aria-hidden="true" /><span>Delete report</span></button></footer></article>)}
      {data.next_offset != null && <button className="button secondary" onClick={() => setParams({ ...Object.fromEntries(params), offset: String(data.next_offset) })}>Next reports</button>}
    </section>}
  </main>
}
