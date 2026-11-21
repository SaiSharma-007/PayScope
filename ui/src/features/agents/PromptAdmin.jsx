import { useCallback, useEffect, useRef, useState } from 'react'
import { request } from '../../lib/http'
import { useAuth } from '../auth/useAuth'
import { useUnsavedChanges } from '../compensation/useUnsavedChanges'
import './agents.css'

const catalog = '/admin/agent-prompts'
const names = { answer_writer: 'Answer Writer', pay_analyst: 'Pay Analyst' }
const stamp = (date) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(date))

function PromptEditor({ agent, onDenied, onDirty }) {
  const { session, expire } = useAuth()
  const [loaded, setLoaded] = useState(null)
  const [active, setActive] = useState(null)
  const [history, setHistory] = useState(null)
  const [body, setBody] = useState('')
  const [note, setNote] = useState('')
  const [review, setReview] = useState(false)
  const [selected, setSelected] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const keepEdits = useRef(false)
  const path = `${catalog}/${agent}`
  const dirty =
    loaded &&
    (body !== (loaded.draft?.body ?? active?.body) ||
      note !== (loaded.draft?.change_note ?? ''))

  useEffect(() => {
    const controller = new AbortController()
    const opts = { signal: controller.signal }
    Promise.all([request(path, opts), request(`${path}/versions`, opts)])
      .then(async ([detail, versions]) => {
        const published = await request(
          `${path}/versions/${detail.active.version}`,
          opts,
        )
        if (controller.signal.aborted) return
        setLoaded(detail)
        setActive(published)
        setHistory(versions)
        if (!keepEdits.current) {
          setBody(detail.draft?.body ?? published.body)
          setNote(detail.draft?.change_note ?? '')
        }
        setConflict(false)
      })
      .catch((problem) => {
        if (!controller.signal.aborted) {
          if (problem.status === 401) expire()
          if (problem.status === 403) onDenied(true)
          setError(problem.message)
        }
      })
    return () => controller.abort()
  }, [path, refresh, expire, onDenied])

  useEffect(() => {
    onDirty(agent, Boolean(dirty))
  }, [agent, dirty, onDirty])

  function problem(error) {
    if (error.status === 401) expire()
    if (error.status === 403) onDenied(true)
    if (error.code === 'PROMPT_CHANGED') setConflict(true)
    setError(error.message)
  }

  async function mutate(action) {
    if (busy || !loaded || conflict) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const isSave = action === 'draft'
      const isRestore = action === 'draft/restore'
      const detail = await request(`${path}/${action}`, {
        method: isSave ? 'PUT' : 'POST',
        csrf: session.csrf_token,
        body: JSON.stringify({
          expected_revision: loaded.edit_revision,
          ...(isSave
            ? { body, change_note: note }
            : isRestore
              ? { version: selected.version }
              : {}),
        }),
      })
      setLoaded(detail)
      setReview(false)
      if (isSave || isRestore) {
        setBody(detail.draft.body)
        setNote(detail.draft.change_note)
        if (isRestore) setSelected(null)
        setMessage(
          isRestore
            ? 'Copied the previous version to a draft.'
            : 'Draft saved.',
        )
      } else {
        setActive({ ...detail.active, body })
        setNote('')
        setSelected(null)
        setHistory((previous) => ({
          ...previous,
          items: [detail.active, ...previous.items],
        }))
        setMessage(`Published v${detail.active.version}.`)
      }
    } catch (error) {
      problem(error)
    } finally {
      setBusy(false)
    }
  }

  async function view(version) {
    setError('')
    try {
      setSelected(await request(`${path}/versions/${version}`))
    } catch (error) {
      problem(error)
    }
  }
  if (!loaded)
    return (
      <section className="agent-panel" aria-label="Prompt editor">
        {error ? (
          <>
            <p role="alert">{error}</p>
            <button
              className="button secondary"
              onClick={() => {
                setError('')
                setRefresh((value) => value + 1)
              }}
            >
              Retry
            </button>
          </>
        ) : (
          <p role="status">Loading prompt…</p>
        )}
      </section>
    )
  return (
    <div className="agent-admin-grid">
      <section className="agent-panel agent-editor" aria-label="Prompt editor">
        <header>
          <div>
            <h2>{names[agent]}</h2>
            <p>{loaded.draft ? 'Saved draft' : 'No saved draft'}</p>
          </div>
          <span className="agent-version">
            Published v{loaded.active.version}
          </span>
        </header>
        {error && (
          <p className="agent-error" role="alert">
            {error}
          </p>
        )}
        {conflict && (
          <button
            className="button secondary"
            onClick={() => {
              keepEdits.current = true
              setError('')
              setReview(false)
              setRefresh((value) => value + 1)
            }}
          >
            Load latest version and keep my edits
          </button>
        )}
        <p className="agent-status" role="status">
          {message}
        </p>
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault()
            mutate('draft')
          }}
        >
          <label htmlFor={`body-${agent}`}>Prompt instructions</label>
          <textarea
            className="resize-none"
            id={`body-${agent}`}
            spellCheck={false}
            value={body}
            maxLength={12000}
            rows={12}
            readOnly={busy}
            onChange={(event) => {
              setBody(event.target.value)
              setReview(false)
            }}
          />
          <label htmlFor={`note-${agent}`}>
            Change note <small>(optional)</small>
          </label>
          <input
            id={`note-${agent}`}
            value={note}
            maxLength={500}
            readOnly={busy}
            onChange={(event) => {
              setNote(event.target.value)
              setReview(false)
            }}
          />
          <div className="agent-actions">
            <button
              className="button primary"
              disabled={!body.trim() || !dirty || busy || conflict}
            >
              Save draft
            </button>
            <button
              type="button"
              className="button secondary"
              disabled={!loaded.draft || dirty || busy || conflict}
              aria-expanded={review}
              onClick={() => setReview(!review)}
            >
              Review draft
            </button>
          </div>
        </form>
        {review && (
          <section
            className="agent-review"
            aria-label="Review before publishing"
          >
            <h3>Review before publishing</h3>
            <div className="agent-compare">
              <div>
                <h4>Published v{active.version}</h4>
                <pre>{active.body}</pre>
              </div>
              <div>
                <h4>Saved draft</h4>
                <pre>{loaded.draft.body}</pre>
              </div>
            </div>
            <button
              className="button primary"
              disabled={busy || conflict}
              onClick={() => mutate('publish')}
            >
              Publish new version
            </button>
          </section>
        )}
      </section>
      <section
        className="agent-panel agent-versions"
        aria-label="Version history"
      >
        <h2>Version history</h2>
        {history.items.map((version) => (
          <button
            key={version.version}
            onClick={() => view(version.version)}
            aria-pressed={selected?.version === version.version}
          >
            <strong>
              v{version.version}{' '}
              {version.version === loaded.active.version && (
                <small>· Published</small>
              )}
            </strong>
            <span>
              {version.author_name || 'System'} · {stamp(version.published_at)}
            </span>
            {version.change_note && <span>{version.change_note}</span>}
          </button>
        ))}
        {history.next_before_version && (
          <button
            onClick={async () => {
              try {
                const page = await request(
                  `${path}/versions?before_version=${history.next_before_version}`,
                )
                setHistory({
                  ...page,
                  items: [...history.items, ...page.items],
                })
              } catch (error) {
                problem(error)
              }
            }}
          >
            Older versions
          </button>
        )}
        {selected && (
          <section
            aria-label={`Version ${selected.version}`}
            className="agent-version-detail"
          >
            <h3>Version {selected.version}</h3>
            <pre>{selected.body}</pre>
            <button
              className="button secondary"
              disabled={busy || conflict || dirty}
              onClick={() => mutate('draft/restore')}
            >
              {loaded.draft ? 'Replace saved draft' : 'Copy to draft'}
            </button>
            {dirty && <p>Save your edits before copying a version.</p>}
          </section>
        )}
      </section>
    </div>
  )
}

export default function PromptAdmin() {
  const { session } = useAuth()
  const [agent, setAgent] = useState('pay_analyst')
  const [denied, setDenied] = useState(false)
  const [visitedWriter, setVisitedWriter] = useState(false)
  const [dirty, setDirty] = useState({})
  const allowed = session.user.manage_agent_prompts && !denied
  const discardDialog = useUnsavedChanges(
    allowed && Object.values(dirty).some(Boolean),
  )
  const recordDirty = useCallback((key, value) => {
    setDirty((previous) =>
      previous[key] === value ? previous : { ...previous, [key]: value },
    )
  }, [])
  return (
    <main id="main" className="page agent-page">
      <header className="agent-heading">
        <div>
          <p>Admin</p>
          <h1 tabIndex={-1}>Agent prompts</h1>
        </div>
      </header>
      {!allowed ? (
        <div className="agent-panel">
          <h2>Prompt access is restricted</h2>
          <p>Your account needs permission to manage agent prompts.</p>
        </div>
      ) : (
        <>
          <div className="agent-tabs" role="group" aria-label="Choose an agent">
            {Object.entries(names)
              .reverse()
              .map(([key, label]) => (
                <button
                  key={key}
                  aria-pressed={key === agent}
                  onClick={() => {
                    if (key === 'answer_writer') setVisitedWriter(true)
                    setAgent(key)
                  }}
                >
                  {label}
                </button>
              ))}
          </div>
          <div hidden={agent !== 'pay_analyst'}>
            <PromptEditor
              agent="pay_analyst"
              onDenied={setDenied}
              onDirty={recordDirty}
            />
          </div>
          {visitedWriter && (
            <div hidden={agent !== 'answer_writer'}>
              <PromptEditor
                agent="answer_writer"
                onDenied={setDenied}
                onDirty={recordDirty}
              />
            </div>
          )}
        </>
      )}
      {discardDialog}
    </main>
  )
}
