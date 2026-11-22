import { Alert } from '../../components/ui/alert'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../../components/ui/collapsible'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '../../components/ui/card'
import { Field, FieldGroup, FieldLabel } from '../../components/ui/field'
import { Input } from '../../components/ui/input'
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from '../../components/ui/input-group'
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from '../../components/ui/sheet'
import { Skeleton } from '../../components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table'
import { Textarea } from '../../components/ui/textarea'
import { formatValue } from '../workspace/insightViews'
import { useEffect, useState } from 'react'
import { ArrowUpRight, ChevronRight, FileChartColumn, Pencil, Search, Trash2 } from 'lucide-react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { useDeleteConfirmation } from '../../components/useDeleteConfirmation'
import { markSaved } from './savedState'
import { request } from '../../lib/http'
import { useAuth } from '../auth/useAuth'
import ReportChart from './ReportChart'
import SelectField from '../../components/SelectField'
import './agents.css'
import './agent-polish.css'

export default function SavedReports() {
  const { key } = useLocation()
  return <SavedReportsView key={key} />
}

function SavedReportsView() {
  const { confirm, confirmation } = useDeleteConfirmation()
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const query = params.toString()
  const { state } = useLocation()
  const search = params.get('q') || ''
  const type = params.get('report_type') || ''
  const libraryLocation = { pathname: '/saved-reports', search: state?.librarySearch || '' }
  const [editing, setEditing] = useState(false)
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
    request(id ? `/saved-reports/${id}` : `/saved-reports?${query}`, { signal: controller.signal }).then((data) => { if (controller.signal.aborted) return; setResult({ key, data }); setError('') }).catch((problem) => { if (!controller.signal.aborted && problem.name !== 'AbortError') { if (problem.status === 401) expire(); setError(problem.message) } })
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
  const filtered = Boolean(search || type)
  const reportType = (report) => report.report_type === 'workforce_headcount' ? 'Workforce headcount' : 'Annual base pay'
  const columns = data?.report?.report_type === 'workforce_headcount' ? [] : [
    ['Currency', 'currency_code'], ['Average', 'mean'], ['Median', 'median'],
    ['Minimum', 'minimum'], ['Maximum', 'maximum'],
  ]
  return (
    <main id="main" className="page agent-page saved-reports-page">
      {confirmation}
      {id ? (
        <Button asChild variant="ghost" className="saved-report-back">
          <Link to={libraryLocation}>Back to saved reports</Link>
        </Button>
      ) : (
        <header className="agent-heading">
          <div><h1>Saved reports</h1><p>Independent snapshots of your verified reports.</p></div>
          <Button asChild variant="secondary"><Link to="/insights/ask">Ask about pay <ArrowUpRight data-icon="inline-end" /></Link></Button>
        </header>
      )}
      {error && !editing && <Alert role="alert">{error}</Alert>}
      {deleted && (
        <Alert role="status">
          Report deleted.
          <Button variant="link" disabled={busy} onClick={async () => {
            if (await mutate(`/saved-reports/${deleted}/restore`, 'POST')) setDeleted(null)
          }}>Undo</Button>
        </Alert>
      )}
      {!id && (
        <form className="saved-reports-filters" onSubmit={(event) => {
          event.preventDefault()
          setParams({ q: String(new FormData(event.currentTarget).get('q')).trim(), report_type: type })
        }}>
          <FieldGroup className="saved-report-search">
            <Field>
              <FieldLabel htmlFor="saved-report-query">Search reports</FieldLabel>
              <InputGroup>
                <InputGroupInput key={search} id="saved-report-query" name="q" type="search" defaultValue={search} placeholder="Find a saved report…" />
                <InputGroupAddon align="inline-end">
                  <InputGroupButton type="submit" variant="default" size="sm" className="saved-search-submit">
                    <Search data-icon="inline-start" aria-hidden="true" /> Search
                  </InputGroupButton>
                </InputGroupAddon>
              </InputGroup>
            </Field>
          </FieldGroup>
          <SelectField id="saved-report-type" label="Report type" value={type} placeholder="All types"
            options={[{ value: 'annual_gross_base', label: 'Annual base pay' }, { value: 'workforce_headcount', label: 'Workforce headcount' }]}
            onChange={(value) => setParams({ q: search, report_type: value })}
          />
          {filtered && <Button type="button" variant="ghost" onClick={(event) => {
            event.currentTarget.form.reset()
            setParams({})
          }}>Clear filters</Button>}
        </form>
      )}
      {id && deleted === id ? null : !data ? error ? (
        <Button variant="secondary" onClick={() => { setError(''); setRevision((value) => value + 1) }}>Retry</Button>
      ) : (
        <div role="status"><span className="sr-only">Loading reports…</span><Skeleton className="h-32 w-full" /></div>
      ) : id ? (
        <Card className="saved-report-detail" key={id}>
          <CardHeader>
            <CardTitle><h1>{data.title}</h1></CardTitle>
            {data.description && <p>{data.description}</p>}
            <p className="saved-report-timestamps">
              {reportType(data.report)} · Generated {new Date(data.generated_at).toLocaleString()} · Saved {new Date(data.saved_at).toLocaleString()} · Revision {data.report.revision}
            </p>
            <div className="saved-report-links">
              <Button asChild><Link to={`/insights/base-pay?${new URLSearchParams({ ...data.report.filters, revision: data.report.revision, report_type: data.report.report_type })}`}>Open current report <ArrowUpRight data-icon="inline-end" /></Link></Button>
              {data.source_available
                ? <Button asChild variant="secondary"><Link to={`/insights/ask?chat=${data.source_conversation_id}`}>Original chat</Link></Button>
                : <p>Original chat deleted</p>}
            </div>
          </CardHeader>
          <CardContent>
            <p className="saved-report-summary">{data.summary}</p>
            <ReportChart report={{ ...data.report, chart_view: data.chart_view }} />
            <Collapsible className="saved-report-values">
              <CollapsibleTrigger asChild>
                <Button type="button" variant="ghost" className="saved-values-toggle">
                  <ChevronRight data-icon="inline-start" aria-hidden="true" /> Exact saved values
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent>
              <Table className="saved-report-table" role="table">
                <TableHeader role="rowgroup"><TableRow role="row">
                  {['Group', 'Employees', ...columns.map(([label]) => label)].map((label) => <TableHead key={label} scope="col" role="columnheader">{label}</TableHead>)}
                </TableRow></TableHeader>
                <TableBody role="rowgroup">{data.report.rows.map((row) => (
                  <TableRow key={row.evidence_id} role="row">
                    <TableHead scope="row" role="rowheader">{row.group_name || 'All matching employees'}</TableHead>
                    <TableCell role="cell" data-label="Employees">{formatValue(row.headcount, 'count')}</TableCell>
                    {columns.map(([label, key]) => (
                      <TableCell role="cell" data-label={label} key={key}>
                        {key === 'currency_code' ? row.currency_code || data.report.currency_code : formatValue(row[key], 'money', row.currency_code || data.report.currency_code)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}</TableBody>
              </Table>
              </CollapsibleContent>
            </Collapsible>
          </CardContent>
          <CardFooter className="saved-report-actions">
            <Sheet open={editing} onOpenChange={(open) => { if (!busy) { setEditing(open); setError('') } }}>
              <SheetTrigger asChild><Button variant="secondary" className="saved-report-edit-action"><Pencil data-icon="inline-start" aria-hidden="true" /> Edit title and description</Button></SheetTrigger>
              <SheetContent className="saved-report-edit" aria-describedby={undefined}>
                <SheetTitle>Edit title and description</SheetTitle>
                <form onSubmit={async (event) => {
                  event.preventDefault()
                  const form = new FormData(event.currentTarget)
                  if (await mutate(`/saved-reports/${id}`, 'PATCH', { title: form.get('title'), description: form.get('description') })) setEditing(false)
                }}>
                  <FieldGroup>
                    <Field><FieldLabel htmlFor="snapshot-title">Title</FieldLabel><Input id="snapshot-title" name="title" defaultValue={data.title} maxLength={160} required /></Field>
                    <Field><FieldLabel htmlFor="snapshot-description">Description</FieldLabel><Textarea id="snapshot-description" name="description" defaultValue={data.description} maxLength={2000} /></Field>
                    {error && <Alert role="alert">{error}</Alert>}
                    <Button disabled={busy}>{busy ? 'Saving…' : 'Save details'}</Button>
                  </FieldGroup>
                </form>
              </SheetContent>
            </Sheet>
            <Button variant="ghost" className="saved-report-delete-action" disabled={busy} onClick={() => confirmReport(data)}><Trash2 data-icon="inline-start" aria-hidden="true" /> Delete report</Button>
          </CardFooter>
        </Card>
      ) : (
        <section className="saved-report-grid" aria-label="Saved report library">
          {!data.items.length && <Alert>{filtered ? 'No reports match these filters.' : 'No saved reports. Save a report from a completed chat response.'}</Alert>}
          {data.items.map((item) => (
            <Card className="saved-report-card" key={item.id}>
              <CardHeader>
                <FileChartColumn className="saved-report-card-icon" aria-hidden="true" />
                <CardTitle><h2><Link to={`/saved-reports/${item.id}`} state={{ librarySearch: query ? `?${query}` : '' }}>{item.title}</Link></h2></CardTitle>
              </CardHeader>
              <CardContent><p>{item.summary || item.description}</p></CardContent>
              <CardFooter className="saved-report-card-footer">
                <small>{reportType(item.report)} · {new Date(item.saved_at).toLocaleDateString()}</small>
                <Button variant="ghost" size="icon-lg" className="saved-report-delete-action saved-report-delete-icon" aria-label="Delete report" title={`Delete ${item.title}`} disabled={busy} onClick={() => confirmReport(item)}><Trash2 /></Button>
              </CardFooter>
            </Card>
          ))}
          {data.next_offset != null && <Button variant="secondary" onClick={() => setParams({ ...Object.fromEntries(params), offset: String(data.next_offset) })}>Next reports</Button>}
        </section>
      )}
    </main>
  )
}
