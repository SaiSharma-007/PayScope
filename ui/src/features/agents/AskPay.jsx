import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowUp,
  ArrowUpRight,
  MessageSquare,
  Plus,
  Square,
  Trash2,
} from 'lucide-react'
import { request } from '../../lib/http'
import { useAuth } from '../auth/useAuth'
import { readEvents } from './stream'
import Activity from './Activity'
import ReportChart from './ReportChart'
import { loadChat, saveChat } from './chatCache'
import './agents.css'

const chatsPath = '/agent/conversations'
const runsPath = '/agent/runs'
const examples = [
  'Which Engineering role in India has the highest median base pay in INR?',
  'What is the average annual base pay in Germany in EUR?',
  'Which department has the lowest median base pay in the US in USD?',
]
const stages = {
  pay_analyst: 'Interpreting the question',
  answer_writer: 'Writing a verified answer',
  get_report_options: 'Looking up report filters',
  get_salary_summary: 'Running the salary report',
}

function ReportCard({ report, conversation }) {
  if (!report) return null
  const params = new URLSearchParams({
    ...report.filters,
    revision: report.revision,
    ...(report.report_type === 'workforce_headcount' ? { report_type: report.report_type } : {}),
    ...(conversation ? { chat: conversation } : {}),
  })
  return (
    <div className="agent-evidence">
      <div>
        <strong>{report.report_type === 'workforce_headcount' ? 'Workforce headcount' : 'Annual base pay'}</strong>
        <span>
          {[report.currency_code, `${report.rows.length} report groups`]
            .filter(Boolean)
            .join(' · ')}
        </span>
      </div>
      <Link to={`/insights/base-pay?${params}`}>
        Open report <ArrowUpRight size={15} aria-hidden="true" />
      </Link>
      <ReportChart report={report} />
      {report.rows.length > 0 && (
        <details>
          <summary>View saved figures</summary>
          <div className="agent-table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Group</th>
                  <th scope="col">Employees</th>
                  {report.report_type !== 'workforce_headcount' && <><th scope="col">Average</th><th scope="col">Median</th></>}
                </tr>
              </thead>
              <tbody>
                {report.rows.map((row) => (
                  <tr key={row.evidence_id}>
                    <th scope="row">
                      {row.group_name || 'All matching employees'}
                    </th>
                    <td>{row.headcount}</td>
                    {report.report_type !== 'workforce_headcount' && <><td>{row.mean}</td><td>{row.median}</td></>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  )
}

function ChatThread({ id, onAccepted, onChanged }) {
  const { session, expire, sessionCache } = useAuth()
  const cacheKey = `${chatsPath}/${id}`
  const [initial] = useState(() => id ? sessionCache.get(cacheKey)?.data : null)
  const [question, setQuestion] = useState(initial?.draft || '')
  const [chat, setChat] = useState(initial || null)
  const [events, setEvents] = useState(() => initial?.active_run_id ? initial.turns.find((turn) => turn.run_id === initial.active_run_id)?.events || [] : [])
  const [pending, setPending] = useState(null)
  const [status, setStatus] = useState(initial?.active_run_id ? 'streaming' : id && !initial ? 'loading' : 'ready')
  const [error, setError] = useState('')
  const [stopping, setStopping] = useState(false)
  const [revision, setRevision] = useState(0)
  const controller = useRef(null)
  const cursor = useRef(events.at(-1)?.sequence || 0)
  const adoptedId = useRef(null)
  const actions = useRef({ onAccepted, onChanged })
  const input = useRef(null)
  const messages = useRef(null)
  const atEnd = useRef(true)
  useEffect(() => {
    actions.current = { onAccepted, onChanged }
  }, [onAccepted, onChanged])

  function receiveError(problem) {
    if (problem.name === 'AbortError') return
    if (problem.status === 401) expire()
    setError(problem.message)
  }

  async function follow(path, options, signal, adopt = false) {
    const response = await request(path, { ...options, stream: true, signal })
    if (!response.body)
      throw new Error(
        'The response stream is unavailable. Reconnect to try again.',
      )
    let finished = false
    for await (const event of readEvents(response.body)) {
      if (signal.aborted) return
      if (event.type === 'accepted' && adopt && event.payload.conversation_id) {
        adoptedId.current = event.payload.conversation_id
        actions.current.onAccepted(event.payload.conversation_id)
      }
      if (event.sequence <= cursor.current) continue
      cursor.current = event.sequence
      setEvents((previous) => [...previous, event])
      if (event.type === 'final') {
        finished = true
        setStatus('ready')
        actions.current.onChanged()
        break
      }
    }
    if (!signal.aborted && !finished) setStatus('disconnected')
  }

  useEffect(() => {
    if (id && id === adoptedId.current) return
    const owned = new AbortController()
    controller.current = owned
    if (id) {
      loadChat(sessionCache, cacheKey)
        .then(async (result) => {
          if (owned.signal.aborted) return
          setChat(result)
          setStatus(result.active_run_id ? 'streaming' : 'ready')
          if (result.active_run_id)
            await follow(
              `${runsPath}/${result.active_run_id}/events?after=${cursor.current}`,
              {},
              owned.signal,
            )
        })
        .catch((problem) => {
          if (owned.signal.aborted) return
          receiveError(problem)
          setStatus(cursor.current ? 'disconnected' : 'load-error')
        })
    }
    return () => {
      owned.abort()
    }
    // Each chat owns its subscription. Callback changes do not restart a stream.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, revision])
  useEffect(() => () => controller.current?.abort(), [])

  const finalEvent = events.findLast((event) => event.type === 'final')
  const run = finalEvent?.run_id || events[0]?.run_id || chat?.active_run_id
  const activeTurn = chat?.turns.find((turn) => turn.run_id === run)
  const latest = chat?.turns.at(-1)
  const prompt =
    pending?.body.question ||
    activeTurn?.messages.find((message) => message.role === 'user')?.text
  const lastOutput =
    finalEvent?.payload ||
    latest?.messages.find((message) => message.role === 'assistant')
      ?.structured_content
  const lastStatus = finalEvent?.payload.status || latest?.status
  const lastRun = finalEvent?.run_id || latest?.run_id
  const clarification =
    lastStatus === 'awaiting_clarification' ? lastOutput?.clarification : null
  const streaming = status === 'streaming'

  useEffect(() => {
    if (!id || status === 'loading' || status === 'load-error') return
    const current = run && events.length ? {
      run_id: run,
      status: finalEvent?.payload.status || 'running',
      events,
      messages: [
        { role: 'user', text: prompt },
        ...(finalEvent ? [{ role: 'assistant', text: finalEvent.payload.answer, structured_content: finalEvent.payload }] : []),
      ],
    } : null
    saveChat(sessionCache, cacheKey, {
      ...chat,
      id,
      draft: question,
      active_run_id: streaming || status === 'disconnected' ? run : null,
      turns: current ? [...(chat?.turns || []).filter((turn) => turn.run_id !== run), current] : chat?.turns || [],
    })
  }, [id, cacheKey, sessionCache, chat, events, finalEvent, run, prompt, question, streaming, status])

  async function send(
    text,
    kind = 'question',
    parent = null,
    retryPending = null,
  ) {
    if (!text.trim() || streaming) return
    controller.current?.abort()
    const owned = new AbortController()
    controller.current = owned
    const submission = retryPending || {
      key: crypto.randomUUID(),
      body: {
        question: text.trim(),
        ...(id ? { conversation_id: id } : {}),
        ...(parent ? { kind, parent_run_id: parent } : {}),
      },
    }
    if (finalEvent && !retryPending) {
      const ended = activeTurn || {
        run_id: finalEvent.run_id,
        messages: [{ role: 'user', text: prompt }],
      }
      const archived = {
        ...ended,
        events,
        status: finalEvent.payload.status,
        messages: [
          ...ended.messages.filter((message) => message.role === 'user'),
          {
            role: 'assistant',
            text: finalEvent.payload.answer,
            structured_content: finalEvent.payload,
          },
        ],
      }
      setChat((previous) => ({
        ...previous,
        active_run_id: null,
        turns: [
          ...(previous?.turns || []).filter(
            (item) => item.run_id !== ended.run_id,
          ),
          archived,
        ],
      }))
    }
    setPending(submission)
    setQuestion('')
    setError('')
    setEvents([])
    cursor.current = 0
    setStatus('streaming')
    try {
      await follow(
        runsPath,
        {
          method: 'POST',
          csrf: session.csrf_token,
          headers: { 'Idempotency-Key': submission.key },
          body: JSON.stringify(submission.body),
        },
        owned.signal,
        !id,
      )
    } catch (problem) {
      if (owned.signal.aborted) return
      receiveError(problem)
      if (
        problem.status &&
        problem.code !== 'ADMISSION_PENDING' &&
        !cursor.current
      ) {
        setPending(null)
        setQuestion(submission.body.question)
        setStatus('ready')
      } else setStatus('disconnected')
    }
  }

  async function reconnect() {
    if (!run && pending)
      return send(pending.body.question, 'question', null, pending)
    if (!run) {
      setRevision((value) => value + 1)
      return
    }
    const owned = new AbortController()
    controller.current = owned
    setStatus('streaming')
    setError('')
    try {
      await follow(
        `${runsPath}/${run}/events?after=${cursor.current}`,
        {},
        owned.signal,
      )
    } catch (problem) {
      if (!owned.signal.aborted) {
        receiveError(problem)
        setStatus('disconnected')
      }
    }
  }

  async function stop() {
    if (!run || stopping) return
    setStopping(true)
    try {
      await request(`${runsPath}/${run}/cancel`, {
        method: 'POST',
        csrf: session.csrf_token,
      })
      if (status === 'disconnected') await reconnect()
    } catch (problem) {
      receiveError(problem)
    } finally {
      setStopping(false)
    }
  }

  async function older() {
    setError('')
    try {
      const result = await request(
        `${chatsPath}/${id}?before_turn=${chat.next_before_turn}`,
      )
      setChat((previous) => ({
        ...previous,
        next_before_turn: result.next_before_turn,
        turns: [...result.turns, ...previous.turns],
      }))
    } catch (problem) {
      receiveError(problem)
    }
  }

  const transcript =
    chat?.turns.filter(
      (turn) => turn.run_id !== run || (!events.length && !chat.active_run_id),
    ) || []
  const answer = finalEvent
    ? finalEvent.payload.answer
    : events
        .filter((event) => event.type === 'token')
        .map((event) => event.payload.text)
        .join('')
  const activeStage = [...events]
    .reverse()
    .find(
      (event) =>
        event.type === 'tool_started' || event.type === 'agent_started',
    )
  const statusText = stopping
    ? 'Stopping…'
    : streaming
      ? stages[activeStage?.payload.tool_name || activeStage?.agent_name] ||
        'Starting the report…'
      : finalEvent
        ? {
            cancelled: 'Request stopped.',
            interrupted: 'Request interrupted.',
            failed: 'Request failed.',
            awaiting_clarification: 'Waiting for your answer.',
          }[lastStatus] || 'Response finished.'
        : ''
  const sendDisabled = streaming || status !== 'ready'
  useEffect(() => {
    const list = messages.current
    if (list && atEnd.current) list.scrollTop = list.scrollHeight
  }, [events, pending, chat])
  return (
    <section className="agent-panel agent-thread" aria-label="Pay conversation">
      {status === 'loading' && <p role="status">Loading conversation…</p>}
      {status === 'load-error' && (
        <button className="button secondary" onClick={reconnect}>
          Reload conversation
        </button>
      )}
      {!id && !pending && (
        <div className="agent-intro" data-enter>
          <MessageSquare size={30} aria-hidden="true" />
          <h2>What would you like to know about pay?</h2>
          <p>
            Ask about current annual base pay by country, department, or job
            title.
          </p>
          <div className="agent-examples">
            {examples.map((example) => (
              <button
                type="button"
                key={example}
                onClick={() => {
                  setQuestion(example)
                  input.current?.focus()
                }}
              >
                {example}
                <ArrowUpRight size={16} aria-hidden="true" />
              </button>
            ))}
          </div>
        </div>
      )}
      {chat?.next_before_turn && (
        <button className="button secondary" onClick={older}>
          Load earlier messages
        </button>
      )}
      <div
        className="agent-messages"
        ref={messages}
        tabIndex={transcript.length || prompt || events.length ? 0 : undefined}
        aria-label="Messages"
        role="region"
        onScroll={(event) => {
          const list = event.currentTarget
          atEnd.current =
            list.scrollHeight - list.clientHeight - list.scrollTop < 36
        }}
      >
        {transcript.map((turn) => (
          <div key={turn.run_id}>
            {turn.messages.map((message) => (
              <div
                key={message.role}
                className={`agent-message ${message.role}`}
              >
                <strong>{message.role === 'user' ? 'You' : 'PayScope'}</strong>
                {message.role === 'assistant' && <Activity events={turn.events || []} status={turn.status} />}
                <p>{message.text || (message.role === 'assistant' ? 'This response ended before an answer was available.' : '')}</p>
                <ReportCard
                  report={message.structured_content?.report}
                  conversation={id}
                />
              </div>
            ))}
            {!turn.messages.some((message) => message.role === 'assistant') && (
              <div className="agent-message assistant">
                <strong>PayScope</strong>
                <Activity events={turn.events || []} status={turn.status} />
                <p>{turn.status === 'cancelled' ? 'Request stopped.' : 'This response was interrupted before an answer was available.'}</p>
              </div>
            )}
          </div>
        ))}
        {prompt && (
          <div className="agent-message user">
            <strong>You</strong>
            <p>{prompt}</p>
          </div>
        )}
        {(answer || events.length > 0 || streaming) && (
          <div className="agent-message assistant">
            <strong>PayScope</strong>
            <Activity events={events} active={streaming} status={lastStatus} />
            {streaming && !answer && <p className="agent-working">{statusText}</p>}
            <p>{answer}</p>
            <ReportCard
              report={
                finalEvent?.payload.report ||
                (!finalEvent
                  ? events.findLast((event) => event.type === 'report_ready')
                      ?.payload
                  : null)
              }
              conversation={id}
            />
          </div>
        )}
      </div>
      <p className="agent-status" role="status">
        {statusText}
      </p>
      {error && (
        <p className="agent-error" role="alert">
          {error}
        </p>
      )}
      {status === 'disconnected' && (
        <div className="agent-actions">
          <span>Connection interrupted.</span>
          <button className="button secondary" onClick={reconnect}>
            Reconnect
          </button>
        </div>
      )}
      {clarification && !streaming && (
        <div className="agent-actions">
          {clarification.choices.map((choice) => (
            <button
              className="button secondary"
              key={choice}
              onClick={() => send(choice, 'clarification', lastRun)}
            >
              {choice}
            </button>
          ))}
        </div>
      )}
      {!streaming &&
        ['failed', 'interrupted', 'cancelled'].includes(lastStatus) && (
          <button
            className="button secondary"
            onClick={() =>
              send(prompt || latest.messages[0].text, 'retry', lastRun)
            }
          >
            Retry question
          </button>
        )}
      <form
        noValidate
        className="agent-composer"
        onSubmit={(event) => {
          event.preventDefault()
          send(
            question,
            clarification ? 'clarification' : 'question',
            clarification ? lastRun : null,
          )
        }}
      >
        <label htmlFor="pay-question">
          {clarification ? 'Answer the clarification' : 'Your pay question'}
        </label>
        <div>
          <textarea
            className="resize-none"
            ref={input}
            id="pay-question"
            value={question}
            maxLength={2000}
            rows={2}
            disabled={status === 'loading' || status === 'load-error'}
            placeholder="Ask about pay, compare teams, or follow up…"
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                if (!sendDisabled) event.currentTarget.form.requestSubmit()
              }
            }}
            onChange={(event) => setQuestion(event.target.value)}
          />
          {(streaming || status === 'disconnected') && run ? (
            <button
              type="button"
              className="button secondary"
              onClick={stop}
              disabled={stopping}
            >
              <Square size={15} aria-hidden="true" /> Stop
            </button>
          ) : (
            <button
              className="button primary"
              disabled={sendDisabled || !question.trim()}
            >
              <ArrowUp size={17} aria-hidden="true" /> Ask
            </button>
          )}
        </div>
        <small>Enter to send · Shift + Enter for a new line</small>
      </form>
    </section>
  )
}

export default function AskPay() {
  const [parameters, setParameters] = useSearchParams()
  const id = parameters.get('chat')
  const { expire, session, sessionCache } = useAuth()
  const [history, setHistory] = useState(() => sessionCache.get(chatsPath)?.data || null)
  const [err, setErr] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [newChat, setNewChat] = useState(0)
  const [adopted, setAdopted] = useState(null)
  const [deleted, setDeleted] = useState(null)
  const [deleting, setDeleting] = useState(null)
  useEffect(() => {
    const controller = new AbortController()
    loadChat(sessionCache, chatsPath)
      .then((result) => {
        if (controller.signal.aborted) return
        setHistory(result)
        setErr('')
      })
      .catch((problem) => {
        if (!controller.signal.aborted && problem.name !== 'AbortError') {
          if (problem.status === 401) expire()
          setErr(problem.message)
        }
      })
    return () => controller.abort()
  }, [refresh, expire, sessionCache])
  function refreshHistory() {
    sessionCache.delete(chatsPath)
    setRefresh((value) => value + 1)
  }
  async function removeChat(chat) {
    setDeleting(chat.id)
    setErr('')
    try {
      await request(`${chatsPath}/${chat.id}`, { method: 'DELETE', csrf: session.csrf_token })
      sessionCache.delete(`${chatsPath}/${chat.id}`)
      const next = { ...history, items: history.items.filter((item) => item.id !== chat.id) }
      setHistory(next)
      saveChat(sessionCache, chatsPath, next)
      setRefresh((value) => value + 1)
      setDeleted(chat)
      if (id === chat.id) {
        setNewChat((value) => value + 1)
        setParameters({}, { replace: true })
      }
    } catch (problem) {
      if (problem.status === 401) expire()
      setErr(problem.message)
    } finally {
      setDeleting(null)
    }
  }
  function select(chat, replace = false) {
    setParameters(chat ? { chat } : {}, { replace })
  }
  return (
    <main id="main" className="page agent-page agent-chat-page">
      <header className="agent-heading">
        <div>
          <Link to="/insights">Salary insights</Link>
          <h1 tabIndex={-1}>Ask about pay</h1>
        </div>
        <button
          className="button secondary"
          onClick={() => {
            setNewChat((value) => value + 1)
            select(null)
          }}
        >
          <Plus size={17} aria-hidden="true" /> New chat
        </button>
      </header>
      <div className="agent-workspace">
        <nav
          className="agent-panel agent-history"
          aria-label="Saved conversations"
        >
          <h2>Conversations</h2>
          {!history && !err && <p>Loading…</p>}
          {err && (
            <p role="alert">
              {err}{' '}
              <button onClick={refreshHistory}>
                Retry
              </button>
            </p>
          )}
          {history?.items.length === 0 && <p>Your chats will appear here.</p>}
          {deleted && <p role="status">Chat deleted. <button className="insight-text-button" disabled={Boolean(deleting)} onClick={async () => {
            setDeleting(deleted.id)
            try {
              await request(`${chatsPath}/${deleted.id}/restore`, { method: 'POST', csrf: session.csrf_token })
              setDeleted(null)
              refreshHistory()
            } catch (problem) {
              if (problem.status === 401) expire()
              setErr(problem.message)
            } finally { setDeleting(null) }
          }}>Undo</button></p>}
          {history?.items.map((chat) => (
            <div className="agent-history-row" key={chat.id}>
            <Link
              to={`?chat=${chat.id}`}
              aria-current={id === chat.id ? 'page' : undefined}
            >
              {chat.title}
            </Link>
            <button type="button" className="icon-button" aria-label={`Delete chat: ${chat.title}`} title="Delete chat" disabled={Boolean(deleting) || Boolean(chat.active_run_id)} onClick={() => removeChat(chat)}><Trash2 size={16} aria-hidden="true" /></button>
            </div>
          ))}
          {history?.next_offset != null && (
            <button
              className="button secondary"
              onClick={async () => {
                try {
                  const next = await request(
                    `${chatsPath}?offset=${history.next_offset}`,
                  )
                  const combined = {
                    ...next,
                    items: [
                      ...history.items,
                      ...next.items.filter(
                        (chat) =>
                          !history.items.some((item) => item.id === chat.id),
                      ),
                    ],
                  }
                  setHistory(combined)
                  saveChat(sessionCache, chatsPath, combined)
                } catch (problem) {
                  setErr(problem.message)
                }
              }}
            >
              More chats
            </button>
          )}
        </nav>
        <ChatThread
          key={id && id !== adopted ? id : `new-${newChat}`}
          id={id}
          onAccepted={(chat) => {
            setAdopted(chat)
            select(chat, true)
            refreshHistory()
          }}
          onChanged={refreshHistory}
        />
      </div>
    </main>
  )
}
