import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'
import { Spinner } from '../../components/ui/spinner'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Save } from 'lucide-react'
import SelectField from '../../components/SelectField'
import ComponentEditor from './ComponentEditor'
import Breakdown from './Breakdown'
import { DiscardDialog } from './DiscardDialog'
import { useUnsavedChanges } from './useUnsavedChanges'
import { ErrorSummary, FormField } from './Fields'
import {
  errorsFor,
  today,
  toDefinition,
  useCompensationApi,
  useReferenceData,
} from './shared'

const empty = () => ({
  name: '',
  country_code: 'IN',
  currency_code: 'INR',
  components: [],
})

export default function RuleEditor() {
  const { ruleId } = useParams()
  const [params, setParams] = useSearchParams()
  const versionId = params.get('version')
  const navigate = useNavigate()
  const api = useCompensationApi()
  const reference = useReferenceData()
  const [draft, setDraft] = useState(empty)
  const [baseline, setBaseline] = useState(() => JSON.stringify(empty()))
  const [record, setRecord] = useState(null)
  const [editing, setEditing] = useState(!ruleId)
  const [loading, setLoading] = useState(!!ruleId)
  const [error, setError] = useState(null)
  const [retry, setRetry] = useState(0)
  const [busy, setBusy] = useState(false)
  const [samplePay, setSamplePay] = useState('1000000')
  const [preview, setPreview] = useState(null)
  const [previewError, setPreviewError] = useState(null)
  const [previewBusy, setPreviewBusy] = useState(false)
  const pendingNavigation = useRef(null)
  const [discard, setDiscard] = useState(null)
  const submitLock = useRef(false)
  const dirty = JSON.stringify(draft) !== baseline
  const navigationGuard = useUnsavedChanges(dirty)
  useEffect(() => {
    if (!ruleId) return
    const controller = new AbortController()
    api(`/compensation/rules/${ruleId}`, { signal: controller.signal })
      .then(async (metadata) => {
        const selected = versionId || metadata.rule.version_id
        if (!metadata.versions.some((version) => version.id === selected))
          throw new Error('This version does not belong to the selected rule.')
        const version = await api(`/compensation/versions/${selected}`, {
          signal: controller.signal,
        })
        if (controller.signal.aborted) return
        const next = {
          name: version.name,
          country_code: version.country_code,
          currency_code: version.currency_code,
          components: version.components.map(toDefinition),
        }
        setRecord({ ...metadata, version })
        setDraft(next)
        setBaseline(JSON.stringify(next))
        setEditing(false)
        setPreview(null)
        setError(null)
        setLoading(false)
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setError(error)
          setLoading(false)
        }
      })
    return () => controller.abort()
  }, [api, ruleId, versionId, retry])
  useEffect(() => {
    if (pendingNavigation.current && !dirty) {
      const destination = pendingNavigation.current
      pendingNavigation.current = null
      navigate(`/rules/${destination}`, { replace: true })
    }
  }, [dirty, navigate])
  const previewKey = JSON.stringify([samplePay, draft.currency_code, draft.components])
  const currentPreview = preview?.key === previewKey ? preview.result : null

  function change(patch) {
    setDraft((previous) => ({ ...previous, ...patch }))
    setError(null)
    setPreviewError(null)
  }
  async function save(event) {
    event.preventDefault()
    if (submitLock.current || (ruleId && !dirty)) return
    submitLock.current = true
    setBusy(true)
    setError(null)
    try {
      const result = await api(
        ruleId
          ? `/compensation/rules/${ruleId}/versions`
          : '/compensation/rules',
        {
          method: 'POST',
          body: JSON.stringify({
            ...draft,
            ...(ruleId ? { expected_version: record.rule.latest_version } : {}),
          }),
        },
      )
      pendingNavigation.current = result.rule_id
      setBaseline(JSON.stringify(draft))
      if (ruleId) {
        setEditing(false)
        setRetry((value) => value + 1)
      }
    } catch (error) {
      setError(error)
      requestAnimationFrame(() =>
        document.querySelector('.comp-error')?.focus(),
      )
    } finally {
      setBusy(false)
      submitLock.current = false
    }
  }
  async function calculatePreview() {
    if (previewBusy) return
    setPreviewBusy(true)
    setPreviewError(null)
    try {
      const result = await api('/compensation/preview', {
        method: 'POST',
        body: JSON.stringify({
          annual_basic_pay: samplePay,
          currency_code: draft.currency_code,
          effective_date: today(),
          components: draft.components,
        }),
      })
      setPreview({ key: previewKey, result })
    } catch (error) {
      setPreviewError(error)
    } finally {
      setPreviewBusy(false)
    }
  }
  async function toggleStatus() {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await api(`/compensation/rules/${ruleId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          active: !record.rule.active,
          expected_version: record.rule.latest_version,
        }),
      })
      setRetry((value) => value + 1)
    } catch (error) {
      setError(error)
    } finally {
      setBusy(false)
    }
  }
  function reload() {
    setLoading(true)
    setRetry((value) => value + 1)
    setDiscard(null)
  }
  function requestReload() {
    if (dirty) setDiscard('reload')
    else reload()
  }
  return (
    <main id="main" className="page rule-editor-page">
      {navigationGuard}
      <DiscardDialog
        open={!!discard}
        onCancel={() => setDiscard(null)}
        onDiscard={() => {
          if (discard === 'reload') reload()
          else {
            setDraft(JSON.parse(baseline))
            setEditing(false)
            setPreview(null)
            setDiscard(null)
          }
        }}
      />
      <Button asChild variant="outline" className="comp-back rule-header-control">
        <Link to="/rules">
          <ArrowLeft data-icon="inline-start" aria-hidden="true" />
          All compensation rules
        </Link>
      </Button>
      <div className="workspace-heading">
        <div>

          <h1>
            {ruleId
              ? record?.version.name || 'Compensation rule'
              : 'New compensation rule'}
          </h1>
        </div>
        {record && !editing && (
          <Button
            variant="outline"
            className="rule-header-control"
            disabled={busy}
            onClick={toggleStatus}
          >
            {busy
              ? 'Updating…'
              : record.rule.active
                ? 'Deactivate rule'
                : 'Reactivate rule'}
          </Button>
        )}
      </div>
      {record && (
        <div className="rule-version-bar">
        {record && !editing && (
          <SelectField
            id="rule-version-history"
            label="Inspect version"
            value={record.version.id}
            options={record.versions.map((version) => ({
              value: version.id,
              label: `Version ${version.number} · ${new Date(version.created_at).toLocaleDateString()}`,
            }))}
            onChange={(value) => {
              setLoading(true)
              setParams({ version: value })
            }}
          />
        )}
          {editing && <span className="rule-state">Draft version {record.rule.latest_version + 1}</span>}
        </div>
      )}
      {loading ? (
        <section className="panel comp-loading" role="status">
          Loading the saved rule…
        </section>
      ) : error && ruleId && !record ? (
        <section className="panel comp-loading">
          <ErrorSummary error={error} />
          <Button variant="secondary" onClick={reload}>
            Try again
          </Button>
        </section>
      ) : (
        <div className="rule-editor-grid">
          <section className="panel rule-definition-panel">
            <form onSubmit={save} noValidate>
              <ErrorSummary error={error} onReload={requestReload} />
              <ErrorSummary error={reference.error} />
              {reference.error && (
                <Button
                  type="button"
                  className="text-link"
                  onClick={reference.retry}
                >
                  Retry reference data
                </Button>
              )}
              <div className="comp-section-heading">
                <div>
                  <h2>
                    {editing
                      ? ruleId
                        ? 'New rule version'
                        : 'Rule details'
                      : 'Saved definition'}
                  </h2>
                  <p>
                    {ruleId
                      ? 'Publishing a new version leaves existing packages unchanged.'
                      : 'Choose where this structure applies.'}
                  </p>
                </div>
                {record && (
                  <span
                    className={`rule-state${record.rule.active ? ' is-active' : ''}`}
                  >
                    {record.rule.active ? 'Active' : 'Inactive'}
                  </span>
                )}
              </div>
              <div className="rule-metadata">
                <FormField
                  id="rule-name"
                  label="Rule name"
                  value={draft.name}
                  onChange={(event) => change({ name: event.target.value })}
                  disabled={!editing || busy || previewBusy}
                  maxLength={100}
                  error={errorsFor(error, 'name')}
                  placeholder="India · Standard package"
                />
                <SelectField
                  id="rule-country"
                  label="Country"
                  value={draft.country_code}
                  options={(reference.data?.countries || []).map((item) => ({
                    value: item.code,
                    label: item.name,
                  }))}
                  disabled={
                    !editing ||
                    !!ruleId ||
                    !reference.data ||
                    busy ||
                    previewBusy
                  }
                  onChange={(value) => change({ country_code: value })}
                />
                <SelectField
                  id="rule-currency"
                  label="Currency"
                  value={draft.currency_code}
                  options={(reference.data?.currencies || []).map((item) => ({
                    value: item.code,
                    label: item.code,
                  }))}
                  disabled={
                    !editing ||
                    !!ruleId ||
                    !reference.data ||
                    busy ||
                    previewBusy
                  }
                  onChange={(value) => change({ currency_code: value })}
                />
              </div>
              {editing ? (
                <ComponentEditor
                  components={draft.components}
                  onChange={(components) => change({ components })}
                  error={error || previewError}
                  disabled={busy || previewBusy}
                />
              ) : (
                <div className="rule-definition-lines">
                  {draft.components.length === 0 ? (
                    <p>
                      Basic pay only. This rule has no additional components.
                    </p>
                  ) : (
                    draft.components.map((component) => (
                      <div key={component.code}>
                        <div>
                          <strong>{component.label}</strong>
                          <small>
                            {component.code} ·{' '}
                            {component.category.replace('_', ' ')}
                          </small>
                        </div>
                        <div>
                          <strong>
                            {component.method === 'fixed'
                              ? `${draft.currency_code} ${component.value}`
                              : `${component.value}% of basic pay`}
                          </strong>
                          <small>
                            {component.commitment === 'target'
                              ? 'Target / variable'
                              : 'Guaranteed'}{' '}
                            ·{' '}
                            {component.included_in_cost
                              ? 'Included in cost'
                              : 'Excluded from cost'}
                          </small>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
              <div className="comp-actions">
                {editing ? (
                  <>
                    <Button
                      variant="default"
                      type="submit"
                      disabled={
                        busy ||
                        previewBusy ||
                        !reference.data ||
                        (!!ruleId && !dirty)
                      }
                    >
                      <Save size={17} aria-hidden="true" />
                      {busy
                        ? 'Saving…'
                        : ruleId
                          ? `Publish version ${record.rule.latest_version + 1}`
                          : 'Create rule'}
                    </Button>
                    {ruleId && (
                      <Button
                        variant="secondary"
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          dirty ? setDiscard('cancel') : setEditing(false)
                        }
                      >
                        Cancel editing
                      </Button>
                    )}
                  </>
                ) : (
                  <Button
                    variant="default"
                    type="button"
                    disabled={!record?.rule.active || busy}
                    onClick={(event) => {
                      event.preventDefault()
                      setEditing(true)
                    }}
                  >
                    Create new version from v{record?.version.number}
                  </Button>
                )}
              </div>
            </form>
          </section>
          <Card className="rule-preview-panel" aria-labelledby="rule-preview-title">
            <CardHeader>
              <CardTitle><h2 id="rule-preview-title">Calculation preview</h2></CardTitle>
              <CardDescription>Example amounts in {draft.currency_code}.</CardDescription>
            </CardHeader>
            <CardContent>
            <div className="rule-preview-inputs">
              <FormField
                id="rule-preview-basic"
                label={`Example annual basic pay (${draft.currency_code})`}
                value={samplePay}
                inputMode="decimal"
                disabled={previewBusy || busy}
                onChange={(event) => {
                  setSamplePay(event.target.value)
                  setPreviewError(null)
                }}
                error={errorsFor(previewError, 'annual_basic_pay')}
              />
              <Button
                variant="default"
                disabled={previewBusy || busy}
                onClick={calculatePreview}
              >
                {previewBusy && <Spinner data-icon="inline-start" />}
                {previewBusy ? 'Calculating…' : preview ? 'Refresh preview' : 'Preview calculation'}
              </Button>
            </div>
            <ErrorSummary error={previewError} />
            <Breakdown result={currentPreview} title="Example annual breakdown" />
            {preview && !currentPreview && <p className="comp-footnote" role="status">Inputs changed. Refresh the preview to see updated amounts.</p>}
            {!preview && (
              <p className="comp-footnote">
                Fixed amounts and percentages use annual basic pay. Target
                components are shown separately from guaranteed costs.
              </p>
            )}
            </CardContent>
          </Card>
        </div>
      )}
    </main>
  )
}
