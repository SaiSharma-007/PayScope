import { useRef, useState } from 'react'
import { Bookmark, BookmarkCheck, ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { markSaved } from './savedState'
import { request } from '../../lib/http'
import { useAuth } from '../auth/useAuth'

export default function SaveReport({ runId, report, chartView, savedId }) {
  const dialog = useRef(null)
  const { session, expire, sessionCache } = useAuth()
  const [saved, setSaved] = useState(savedId || null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (!runId) return null
  const subject = report.report_type === 'workforce_headcount' ? 'workforce headcount' : 'annual base pay'
  const rawTitle = `${report.operation === 'summary' ? '' : report.operation + ' '}${subject}${report.filters.group_by ? ' by ' + report.filters.group_by.replaceAll('_', ' ') : ''}`
  const title = rawTitle.charAt(0).toUpperCase() + rawTitle.slice(1)
  const description = `${report.report_type === 'workforce_headcount' ? 'Employee counts' : 'Recorded annual base pay'} across ${report.rows.length} ${report.rows.length === 1 ? 'group' : 'groups'}${report.currency_code ? ' in ' + report.currency_code : ''}. ${report.operation === 'summary' ? 'Includes exact figures for this selection.' : 'Highlights the ' + report.operation + ' ' + subject + '.'}`
  return <>
    {saved || savedId ? <Link className="agent-report-saved" to={`/saved-reports/${saved || savedId}`}><BookmarkCheck size={16} aria-hidden="true" /> Saved · View report <ArrowUpRight size={14} aria-hidden="true" /></Link> : <button className="button secondary agent-save-button" onClick={() => dialog.current.showModal()}><Bookmark size={16} aria-hidden="true" /> Save report</button>}
    <dialog ref={dialog} className="agent-panel agent-save-dialog" aria-labelledby={`save-${runId}`}>
      <h2 id={`save-${runId}`}>Save report</h2>
      <form noValidate onSubmit={async (event) => {
        event.preventDefault()
        if (busy) return
        const data = new FormData(event.currentTarget)
        setBusy(true); setError('')
        try {
          const result = await request('/saved-reports', { method: 'POST', csrf: session.csrf_token, body: JSON.stringify({ source_run_id: runId, chart_view: chartView, title: data.get('title'), description: data.get('description') }) })
          setSaved(result.id); markSaved(sessionCache, runId, result.id); dialog.current.close()
        } catch (problem) { if (problem.status === 401) expire(); setError(problem.message) }
        finally { setBusy(false) }
      }}>
        <label>Title<input name="title" defaultValue={title} maxLength={160} required /></label>
        <label>Description<textarea name="description" className="resize-none" defaultValue={description} maxLength={2000} rows={3} /></label>
        <p>Saved figures remain available even if the original chat is deleted.</p>
        {error && <p role="alert">{error}</p>}
        <div className="agent-dialog-actions"><button className="button primary" disabled={busy}>{busy ? 'Saving…' : 'Save report'}</button>
        <button type="button" className="button secondary" disabled={busy} onClick={() => dialog.current.close()}>Cancel</button></div>
      </form>
    </dialog>
  </>
}
