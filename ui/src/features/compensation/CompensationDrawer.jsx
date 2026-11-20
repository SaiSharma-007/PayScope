import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, X } from 'lucide-react'
import SelectField from '../../components/SelectField'
import { SelectPortalContext } from '../../components/SelectPortalContext'
import ComponentEditor from './ComponentEditor'
import Breakdown from './Breakdown'
import EquityPanel from './EquityPanel'
import { DiscardDialog } from './DiscardDialog'
import { useUnsavedChanges } from './useUnsavedChanges'
import { ErrorSummary, FormField } from './Fields'
import {
  errorsFor,
  money,
  today,
  toDefinition,
  useCompensationApi,
  useReferenceData,
} from './shared'

const initial = () => ({
  annual_basic_pay: '',
  currency_code: 'INR',
  effective_date: today(),
  rule_version_id: null,
  components: [],
  overrides: [],
})

export default function CompensationDrawer({ employee, onClose, onSaved }) {
  const api = useCompensationApi()
  const reference = useReferenceData()
  const dialog = useRef(null)
  const [portalContainer, setPortalContainer] = useState(null)
  const attachDialog = useCallback((element) => {
    dialog.current = element
    setPortalContainer(element)
  }, [])
  const closeButton = useRef(null)
  const review = useRef(null)
  const submitLock = useRef(false)
  const [draft, setDraft] = useState(initial)
  const [baseline, setBaseline] = useState(null)
  const [saved, setSaved] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [equityDirty, setEquityDirty] = useState(false)
  const [equityBusy, setEquityBusy] = useState(false)
  const [error, setError] = useState(null)
  const [rules, setRules] = useState(null)
  const [rulesError, setRulesError] = useState(null)
  const [definition, setDefinition] = useState(null)
  const [preview, setPreview] = useState(null)
  const [success, setSuccess] = useState(false)
  const [retry, setRetry] = useState(0)
  const [ruleRetry, setRuleRetry] = useState(0)
  const [discard, setDiscard] = useState(null)
  const serialized = JSON.stringify(draft)
  const dirty = baseline !== null && serialized !== baseline
  const previewReady = preview?.key === serialized
  const navigationGuard = useUnsavedChanges(
    dirty || equityDirty || equityBusy || busy,
  )
  useEffect(() => {
    if (previewReady && review.current) {
      review.current.focus({ preventScroll: true })
      review.current.scrollIntoView({ block: 'start' })
    }
  }, [previewReady])
  const isRule = !!draft.rule_version_id
  useEffect(() => {
    const trigger = document.activeElement
    const element = dialog.current
    element.showModal()
    closeButton.current.focus()
    return () => {
      element.close()
      if (trigger?.isConnected) trigger.focus({ preventScroll: true })
    }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    api(`/employees/${employee.id}/compensation`, { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return
        const next = result
          ? {
              annual_basic_pay: result.annual_basic_pay,
              currency_code: result.currency_code,
              effective_date: result.effective_date,
              rule_version_id: result.rule_version_id,
              components: result.rule_version_id
                ? []
                : result.components.map(toDefinition),
              overrides: result.components
                .filter((line) => line.override_reason)
                .map((line) => ({
                  code: line.code,
                  amount: line.amount,
                  reason: line.override_reason,
                })),
            }
          : {
              ...initial(),
              currency_code: employee.salary?.currency_code || 'INR',
            }
        setDraft(next)
        setBaseline(JSON.stringify(next))
        setSaved(result)
        setError(null)
        setLoading(false)
        setPreview(null)
        setSuccess(false)
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setError(error)
          setLoading(false)
        }
      })
    return () => controller.abort()
  }, [api, employee.id, employee.salary?.currency_code, retry])
  useEffect(() => {
    if (loading) return
    const controller = new AbortController()
    const suffix = `country_code=${employee.country_code}&currency_code=${draft.currency_code}&active=true`
    api(`/compensation/rules?${suffix}`, { signal: controller.signal })
      .then(async (first) => {
        const rest = await Promise.all(
          Array.from(
            { length: Math.max(0, Math.ceil(first.total / 50) - 1) },
            (_, i) =>
              api(`/compensation/rules?${suffix}&page=${i + 2}`, {
                signal: controller.signal,
              }),
          ),
        )
        if (!controller.signal.aborted) {
          setRules([...first.items, ...rest.flatMap((page) => page.items)])
          setRulesError(null)
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) setRulesError(error)
      })
    return () => controller.abort()
  }, [api, employee.country_code, draft.currency_code, loading, ruleRetry])
  useEffect(() => {
    if (!draft.rule_version_id) return
    const controller = new AbortController()
    api(`/compensation/versions/${draft.rule_version_id}`, {
      signal: controller.signal,
    })
      .then((result) => {
        if (!controller.signal.aborted) {
          setDefinition({ id: result.id, components: result.components })
          setRulesError(null)
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) setRulesError(error)
      })
    return () => controller.abort()
  }, [api, draft.rule_version_id, ruleRetry])
  function change(patch) {
    setDraft((previous) => ({ ...previous, ...patch }))
    setPreview(null)
    setSuccess(false)
    setError(null)
  }
  function close() {
    if (busy || equityBusy) return
    if (dirty || equityDirty) setDiscard('close')
    else onClose()
  }
  function reload() {
    setDiscard(null)
    setLoading(true)
    setRetry((value) => value + 1)
  }
  function requestReload() {
    if (dirty) setDiscard('reload')
    else reload()
  }
  async function calculatePreview(event) {
    event.preventDefault()
    if (submitLock.current || equityDirty || equityBusy) return
    submitLock.current = true
    setBusy(true)
    setError(null)
    try {
      const result = await api(
        `/employees/${employee.id}/compensation/preview`,
        { method: 'POST', body: serialized },
      )
      setPreview({ key: serialized, result })
    } catch (error) {
      setError(error)
      requestAnimationFrame(() =>
        dialog.current?.querySelector('.comp-error')?.focus(),
      )
    } finally {
      setBusy(false)
      submitLock.current = false
    }
  }
  async function save() {
    if (
      submitLock.current ||
      equityDirty ||
      equityBusy ||
      preview?.key !== serialized
    )
      return
    submitLock.current = true
    setBusy(true)
    setError(null)
    try {
      const result = await api(`/employees/${employee.id}/compensation`, {
        method: 'PUT',
        body: JSON.stringify({
          ...draft,
          expected_version: saved?.version || 0,
        }),
      })
      setSaved(result)
      setBaseline(serialized)
      setSuccess(true)
      setPreview(null)
      onSaved(result)
    } catch (error) {
      setError(error)
      requestAnimationFrame(() =>
        dialog.current?.querySelector('.comp-error')?.focus(),
      )
    } finally {
      setBusy(false)
      submitLock.current = false
    }
  }
  const definitions = isRule
    ? definition?.id === draft.rule_version_id
      ? definition.components
      : null
    : draft.components
  const options = (rules || []).map((rule) => ({
    value: rule.version_id,
    label: `${rule.name} · v${rule.latest_version}`,
  }))
  if (
    saved?.rule_version_id &&
    !options.some((option) => option.value === saved.rule_version_id)
  )
    options.unshift({
      value: saved.rule_version_id,
      label: `${saved.rule_name} · saved v${saved.rule_number}`,
    })
  return createPortal(
    <>
      {navigationGuard}
      <dialog
        ref={attachDialog}
        className="compensation-drawer"
        aria-labelledby="compensation-title"
        onCancel={(event) => {
          event.preventDefault()
          close()
        }}
      >
        <SelectPortalContext value={portalContainer}>
          <header className="comp-drawer-header">
            <div>
              <span className="eyebrow">EMPLOYEE COMPENSATION</span>
              <h2 id="compensation-title">{employee.full_name}</h2>
              <p>
                {employee.employee_code} · {employee.country_name}
              </p>
            </div>
            <button
              ref={closeButton}
              className="icon-button"
              type="button"
              aria-label="Close compensation"
              disabled={busy || equityBusy}
              onClick={close}
            >
              <X size={20} aria-hidden="true" />
            </button>
          </header>
          {loading ? (
            <div className="comp-loading" role="status">
              Loading compensation…
            </div>
          ) : (
            <form noValidate onSubmit={calculatePreview}>
              <div className="comp-drawer-content">
                <ErrorSummary error={error} onReload={requestReload} />
                {!baseline && error && (
                  <button
                    className="button secondary"
                    type="button"
                    onClick={reload}
                  >
                    Try again
                  </button>
                )}
                {baseline && (
                  <>
                    <div className="package-context">
                      {saved ? (
                        <>
                          <span className="rule-state is-active">
                            Saved package · v{saved.version}
                          </span>
                          <p className="package-rule-meta">
                            {saved.rule_name
                              ? `${saved.rule_name} · rule v${saved.rule_number}`
                              : 'Manual breakdown'}{' '}
                            · saved{' '}
                            {new Date(saved.updated_at).toLocaleDateString()}
                          </p>
                          <dl className="package-metrics">
                            <div>
                              <dt>Guaranteed annual cost</dt>
                              <dd>
                                {money(
                                  saved.guaranteed_cost,
                                  saved.currency_code,
                                )}
                              </dd>
                            </div>
                            <div>
                              <dt>Annual cost with targets</dt>
                              <dd>
                                {money(saved.target_cost, saved.currency_code)}
                              </dd>
                            </div>
                          </dl>
                          <details className="saved-breakdown">
                            <summary>View saved breakdown</summary>
                            <Breakdown
                              result={saved}
                              title="Saved annual breakdown"
                            />
                          </details>
                          <button
                            type="button"
                            className="equity-jump"
                            onClick={() => {
                              const heading =
                                dialog.current?.querySelector('#equity-heading')
                              heading?.focus({ preventScroll: true })
                              heading?.scrollIntoView({ block: 'start' })
                            }}
                          >
                            Equity and annual CTC
                          </button>
                        </>
                      ) : (
                        <>
                          <strong>Create a compensation breakdown.</strong>
                          <p>
                            {employee.salary
                              ? `Existing recorded total: ${money(employee.salary.annual_gross_base, employee.salary.currency_code)}. Enter basic pay explicitly to create the new breakdown.`
                              : 'No salary has been entered for this employee.'}
                          </p>
                        </>
                      )}
                    </div>
                    {success && (
                      <p className="comp-success" role="status">
                        <Check size={17} aria-hidden="true" />
                        Compensation saved. The directory is updated.
                      </p>
                    )}
                    <ErrorSummary error={reference.error} />
                    {reference.error && (
                      <button
                        type="button"
                        className="text-link"
                        onClick={reference.retry}
                      >
                        Retry reference data
                      </button>
                    )}
                    <fieldset className="comp-edit-fields" disabled={busy}>
                      <legend>Package details</legend>
                      <div className="package-basics">
                        <FormField
                          id="package-basic"
                          label="Annual basic pay"
                          value={draft.annual_basic_pay}
                          inputMode="decimal"
                          error={errorsFor(error, 'annual_basic_pay')}
                          onChange={(event) =>
                            change({ annual_basic_pay: event.target.value })
                          }
                          placeholder="600000.00"
                        />
                        <SelectField
                          id="package-currency"
                          label="Currency"
                          value={draft.currency_code}
                          disabled={busy || !reference.data}
                          options={(reference.data?.currencies || []).map(
                            (item) => ({ value: item.code, label: item.code }),
                          )}
                          onChange={(currency_code) => {
                            setRules(null)
                            change({
                              currency_code,
                              rule_version_id: null,
                              components: [],
                              overrides: [],
                            })
                          }}
                        />
                        <FormField
                          id="package-effective"
                          label="Effective date"
                          type="date"
                          value={draft.effective_date}
                          max={today()}
                          error={errorsFor(error, 'effective_date')}
                          onChange={(event) =>
                            change({ effective_date: event.target.value })
                          }
                          hint="Saves take effect immediately; future dates are unavailable."
                        />
                      </div>
                      <SelectField
                        id="package-rule"
                        label="Apply a compensation rule"
                        value={draft.rule_version_id || ''}
                        placeholder="Manual entry · no rule"
                        options={options}
                        disabled={busy || rules === null}
                        onChange={(value) =>
                          change({
                            rule_version_id: value || null,
                            components: [],
                            overrides: [],
                          })
                        }
                      />
                      <p className="comp-footnote">
                        Rules match {employee.country_name} and{' '}
                        {draft.currency_code}. A new version is applied only
                        when you select it, review, and save.
                      </p>
                      <ErrorSummary error={rulesError} />
                      {rulesError && (
                        <button
                          className="text-link"
                          type="button"
                          onClick={() => setRuleRetry((value) => value + 1)}
                        >
                          Retry rules
                        </button>
                      )}
                      {isRule ? (
                        !definitions ? (
                          <p role="status">Loading rule components…</p>
                        ) : (
                          <section
                            className="package-overrides"
                            aria-labelledby="package-components-title"
                          >
                            <div className="comp-section-heading">
                              <div>
                                <h3 id="package-components-title">
                                  Rule components
                                </h3>
                                <p>
                                  Keep the calculation, or enter an agreed
                                  exception with a reason.
                                </p>
                              </div>
                            </div>
                            <div className="override-list">
                              {definitions.map((component) => {
                                const override = draft.overrides.find(
                                  (item) => item.code === component.code,
                                )
                                const index = draft.overrides.findIndex(
                                  (item) => item.code === component.code,
                                )
                                function updateOverride(patch) {
                                  change({
                                    overrides: draft.overrides.map((item) =>
                                      item.code === component.code
                                        ? { ...item, ...patch }
                                        : item,
                                    ),
                                  })
                                }
                                return (
                                  <div
                                    className="override-card"
                                    data-overridden={!!override}
                                    key={component.code}
                                  >
                                    <div className="override-heading">
                                      <div>
                                        <strong>{component.label}</strong>
                                        <small>
                                          {component.method === 'fixed'
                                            ? `${draft.currency_code} ${component.value} annually`
                                            : `${component.value}% of annual basic pay`}{' '}
                                          ·{' '}
                                          {component.commitment === 'target'
                                            ? 'Target'
                                            : 'Guaranteed'}
                                        </small>
                                      </div>
                                      <label className="comp-checkbox">
                                        <input
                                          type="checkbox"
                                          checked={!!override}
                                          onChange={(event) =>
                                            change({
                                              overrides: event.target.checked
                                                ? [
                                                    ...draft.overrides,
                                                    {
                                                      code: component.code,
                                                      amount: '',
                                                      reason: '',
                                                    },
                                                  ]
                                                : draft.overrides.filter(
                                                    (item) =>
                                                      item.code !==
                                                      component.code,
                                                  ),
                                            })
                                          }
                                        />
                                        Override
                                      </label>
                                    </div>
                                    {override && (
                                      <div className="override-fields">
                                        <FormField
                                          id={`override-${component.code}-amount`}
                                          label="Annual amount"
                                          aria-label={`${component.label} annual override`}
                                          value={override.amount}
                                          inputMode="decimal"
                                          error={errorsFor(
                                            error,
                                            `overrides.${index}.amount`,
                                          )}
                                          onChange={(event) =>
                                            updateOverride({
                                              amount: event.target.value,
                                            })
                                          }
                                        />
                                        <FormField
                                          id={`override-${component.code}-reason`}
                                          label="Override reason"
                                          aria-label={`${component.label} override reason`}
                                          multiline
                                          rows={2}
                                          value={override.reason}
                                          maxLength={300}
                                          error={errorsFor(
                                            error,
                                            `overrides.${index}.reason`,
                                          )}
                                          onChange={(event) =>
                                            updateOverride({
                                              reason: event.target.value,
                                            })
                                          }
                                          placeholder="Reason for this employee’s exception"
                                        />
                                      </div>
                                    )}
                                  </div>
                                )
                              })}
                            </div>
                          </section>
                        )
                      ) : (
                        <ComponentEditor
                          components={draft.components}
                          onChange={(components) =>
                            change({
                              components,
                              overrides: draft.overrides.filter((override) =>
                                components.some(
                                  (component) =>
                                    component.code === override.code,
                                ),
                              ),
                            })
                          }
                          error={error}
                          disabled={busy}
                        />
                      )}
                    </fieldset>
                    {previewReady && (
                      <div
                        ref={review}
                        tabIndex={-1}
                        className="package-review"
                      >
                        <div className="package-comparison">
                          <span>
                            Currently saved:{' '}
                            {saved
                              ? money(
                                  saved.guaranteed_cost,
                                  saved.currency_code,
                                )
                              : 'No package'}
                          </span>
                          <strong>
                            Proposed:{' '}
                            {money(
                              preview.result.guaranteed_cost,
                              preview.result.currency_code,
                            )}
                          </strong>
                        </div>
                        <Breakdown
                          result={preview.result}
                          title="Review before saving"
                        />
                      </div>
                    )}
                    {saved && (
                      <EquityPanel
                        employeeId={employee.id}
                        currencies={reference.data?.currencies || []}
                        packageVersion={saved.version}
                        onDirty={setEquityDirty}
                        onBusy={setEquityBusy}
                      />
                    )}
                  </>
                )}
              </div>
              <footer className="comp-drawer-footer">
                <span>
                  {dirty || equityDirty
                    ? 'Unsaved changes'
                    : saved
                      ? 'All changes saved'
                      : 'New package'}
                </span>
                <div>
                  <button
                    className={`button ${previewReady ? 'secondary' : 'primary'}`}
                    type="submit"
                    disabled={
                      busy ||
                      equityBusy ||
                      equityDirty ||
                      !baseline ||
                      (isRule && !definitions) ||
                      !reference.data
                    }
                  >
                    {busy ? 'Working…' : 'Preview changes'}
                  </button>
                  <button
                    className={`button ${previewReady ? 'primary' : 'secondary'}`}
                    type="button"
                    disabled={
                      busy ||
                      equityBusy ||
                      equityDirty ||
                      preview?.key !== serialized ||
                      !dirty
                    }
                    onClick={save}
                  >
                    Save compensation
                  </button>
                </div>
              </footer>
            </form>
          )}
        </SelectPortalContext>
      </dialog>
      <DiscardDialog
        open={!!discard}
        onCancel={() => setDiscard(null)}
        onDiscard={() => (discard === 'reload' ? reload() : onClose())}
      />
    </>,
    document.body,
  )
}
