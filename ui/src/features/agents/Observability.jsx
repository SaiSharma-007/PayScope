import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { request } from '../../lib/http'
import { useAuth } from '../auth/useAuth'
import Activity from './Activity'
import SelectField from '../../components/SelectField'
import './agents.css'
import './observability.css'
const stamp = value => value ? new Date(value).toLocaleString() : '—'
const duration = row => row.started_at && row.finished_at ? `${((Date.parse(row.finished_at)-Date.parse(row.started_at))/1000).toFixed(1)} s` : '—'
const active = row => ['queued','running'].includes(row?.status)
export default function Observability() {
  const { session, expire } = useAuth()
  const { runId } = useParams()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const allowed = session.user.view_agent_observability
  const query = params.toString()
  useEffect(() => {
    if (!allowed) return
    const controller = new AbortController()
    let timer
    async function read() {
      try {
        const opts = { signal: controller.signal }
        let result
        if (runId) {
          const [detail, tools] = await Promise.all([request(`/admin/agent-runs/${runId}`, opts), request(`/admin/agent-runs/${runId}/tools`, opts)])
          let cursor = 0, items = [], page
          do {
            page = await request(`/admin/agent-runs/${runId}/events?after=${cursor}`, opts)
            items.push(...page.items); cursor = page.next_after
          } while (cursor && !controller.signal.aborted)
          result = { ...detail, tools, events: items.map(e => ({ ...e, type: e.event_type, timestamp: e.created_at })) }
        } else result = await request(`/admin/agent-runs?${query}`, opts)
        if (controller.signal.aborted) return
        setData({ ...result, resource: runId || query }); setError('')
        if (runId && active(result)) timer = setTimeout(read, 5000)
      } catch (problem) { if (!controller.signal.aborted) { if (problem.status === 401) expire(); setError(problem.message) } }
    }
    read()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [allowed, runId, query, revision, expire])
  function filter(key,value) { const next = new URLSearchParams(params); next.delete('before'); next.delete('before_id'); value ? next.set(key,['start','end'].includes(key)?new Date(value).toISOString():value) : next.delete(key); setParams(next); setData(null) }
  return <main id="main" className="page agent-page observability"><header className="agent-heading"><div><p>Admin · Execution history</p><h1 tabIndex={-1}>Agent observability</h1><p>Inspect execution, evidence and the prompts used.</p></div><button className="button secondary" onClick={() => setRevision(v=>v+1)}>Refresh</button></header>
    {!allowed ? <p role="alert">Your account needs observability access.</p> : <>
      {error && <div role="alert">{error} <button className="button secondary" onClick={()=>setRevision(v=>v+1)}>Retry</button></div>}
      {!runId && <form className="observe-filters" onSubmit={e=>{e.preventDefault(); const form=new FormData(e.currentTarget); const next=new URLSearchParams(params); next.delete('before'); next.delete('before_id'); for(const key of ['run_id','owner','model','start','end','version']) {const value=form.get(key); value ? next.set(key,['start','end'].includes(key)?new Date(value).toISOString():value) : next.delete(key)} setParams(next); setData(null)}}>
        <SelectField id="run-status" label="Status" value={params.get('status')||''} placeholder="All statuses" options={['completed','failed','cancelled','interrupted','awaiting_clarification','queued','running'].map(value=>({value,label:value.replaceAll('_',' ')}))} onChange={v=>filter('status',v)}/>
        <SelectField id="run-source" label="Source chat" value={params.get('source')||'all'} options={['all','available','deleted'].map(value=>({value,label:value}))} onChange={v=>filter('source',v)}/>
        <SelectField id="run-role" label="Prompt role" value={params.get('role')||''} placeholder="Choose role" options={[{value:'pay_analyst',label:'Pay Analyst'},{value:'answer_writer',label:'Answer Writer'}]} onChange={v=>filter('role',v)}/>
        <label>Owner ID<input name="owner" defaultValue={params.get('owner')||''}/></label><label>Version<input name="version" type="number" min="1" defaultValue={params.get('version')||''}/></label><label>Model<input name="model" defaultValue={params.get('model')||''}/></label><label>Run ID<input name="run_id" defaultValue={params.get('run_id')||''}/></label><label>From<input type="datetime-local" name="start" defaultValue={params.get('start')?.slice(0,16)||''}/></label><label>To<input type="datetime-local" name="end" defaultValue={params.get('end')?.slice(0,16)||''}/></label><button className="button secondary">Apply filters</button><button type="button" className="button secondary" onClick={()=>{setParams({});setData(null)}}>Clear</button>
      </form>}
      {!data || data.resource !== (runId || query) ? !error && <p role="status">Loading execution history…</p> : runId ? <RunDetail key={runId} data={data} query={query} prompts={session.user.manage_agent_prompts}/> : <section className="agent-panel observe-table"><div className="observe-meta" aria-label="Filtered run totals">{data.summary?.map(item=><span key={item.status}>{item.count} {item.status.replaceAll('_',' ')}{item.duration_samples > 0 && ` · ${Number(item.average_seconds).toFixed(1)} s average (${item.duration_samples} timed)`}</span>)}</div><table><caption>{data.items.length} runs on this page · deleted chats included</caption><thead><tr>{['Started','Question / run','Owner','Status','Duration','Calls / tokens','Prompts'].map(label=><th key={label}>{label}</th>)}</tr></thead><tbody>{data.items.map(row=><tr key={row.id}><td>{stamp(row.created_at)}</td><td><Link to={`/admin/agent-runs/${row.id}?${query}`}>{row.title}</Link><small>{row.id}{row.source_deleted_at && ' · Source chat deleted'}</small></td><td>{row.owner}</td><td>{row.status.replaceAll('_',' ')}</td><td>{duration(row)}</td><td>{row.model_calls} calls<small>{row.input_tokens ?? 'Unknown'} in · {row.output_tokens ?? 'Unknown'} out</small></td><td>Analyst v{row.pay_analyst_version}<small>Writer v{row.answer_writer_version}</small></td></tr>)}</tbody></table>{!data.items.length && <p>No runs match these filters.</p>}{data.next && <button className="button secondary" onClick={()=>{setParams({...Object.fromEntries(params),...data.next});setData(null)}}>Older runs</button>}</section>}
    </>}
  </main>
}
function RunDetail({data,query,prompts}) {
  const [selected,setSelected]=useState(null)
  return <><Link to={`/admin/agent-runs?${query}`}>← Back to runs</Link><section className="agent-panel observe-detail"><header><h2>{data.title}</h2><p>{data.status.replaceAll('_',' ')} · {duration(data)} · {data.owner}</p><small>Run {data.id}</small></header><div className="observe-meta"><span>Started {stamp(data.started_at)}</span>{data.source_deleted_at ? <span>Source chat deleted</span> : <Link to={`/insights/ask?chat=${data.conversation_id}`}>Open source chat</Link>}{data.parent_run_id && <Link to={`/admin/agent-runs/${data.parent_run_id}`}>Previous attempt</Link>}{['pay_analyst','answer_writer'].map(role=><span key={role}>{prompts ? <Link to={`/admin/agent-prompts?agent=${role}&version=${data[`${role}_version`]}`}>{role.replaceAll('_',' ')} v{data[`${role}_version`]}</Link> : `${role} v${data[`${role}_version`]}`}</span>)}</div><Activity events={data.events} active={active(data)} status={data.status}/><div className="observe-trace"><section aria-label="Execution events"><h3>Execution timeline</h3>{data.events.map(event=><button className="observe-event" key={event.sequence} aria-pressed={selected?.sequence===event.sequence} onClick={()=>setSelected(event)}><span>{event.event_type.replaceAll('_',' ')}</span><small>{event.agent_name || 'Workflow'} · {stamp(event.created_at)}</small></button>)}</section><section aria-label="Selected event"><h3>{selected ? selected.event_type.replaceAll('_',' ') : 'Select an event'}</h3>{selected ? <><dl>{Object.entries(selected.payload).filter(([,value])=>value === null || typeof value !== 'object').map(([key,value])=><div key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{value == null ? 'Unavailable' : String(value)}</dd></div>)}</dl><details><summary>Event payload</summary><pre>{JSON.stringify(selected.payload,null,2)}</pre></details></> : <p>Inspect timings, handoffs and validated tool parameters.</p>}</section></div>{data.tools.map(tool=><details key={tool.id}><summary>{tool.tool_name} · {tool.status} · revision {tool.report_revision ?? '—'}</summary><pre>{JSON.stringify({parameters:tool.arguments,result:tool.result,error:tool.error_code},null,2)}</pre></details>)}{data.messages.map(message=><section key={message.role}><h3>{message.role==='user'?'Question':'Answer'}</h3><p className="observe-answer">{message.text}</p></section>)}</section></>
}
