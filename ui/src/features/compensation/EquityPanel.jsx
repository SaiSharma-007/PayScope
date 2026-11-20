import { useEffect, useRef, useState } from 'react'
import { Gem, Plus, Trash2 } from 'lucide-react'
import SelectField from '../../components/SelectField'
import { useWorkspaceReport } from '../workspace/useWorkspaceReport'
import { DiscardDialog } from './DiscardDialog'
import { ErrorSummary, FormField } from './Fields'
import { errorsFor, money, today, useCompensationApi } from './shared'

const kinds = [
  { value: 'rsu', label: 'Restricted stock units' },
  { value: 'option', label: 'Stock options' },
]
const currentYear = () => Number(today().slice(0, 4))
const title = (kind) => kinds.find((item) => item.value === kind)?.label

export default function EquityPanel({
  employeeId,
  currencies,
  packageVersion,
  onDirty,
  onBusy,
}) {
  const api = useCompensationApi()
  const [year, setYear] = useState(currentYear)
  const [editor, setEditor] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [discard, setDiscard] = useState(false)
  const [message, setMessage] = useState('')
  const guard = useRef(false)
  const focusError = useRef(false)
  const trigger = useRef(null)
  const addButton = useRef(null)
  const root = useRef(null)
  const path = `/employees/${employeeId}/equity`
  const report = useWorkspaceReport(
    `${path}?year=${year}&package_version=${packageVersion}`,
  )
  const data = report.data
  const draft = editor?.draft
  const editing = !!editor
  const dirty = !!editor && JSON.stringify(draft) !== editor.baseline

  useEffect(() => {
    onDirty(dirty)
  }, [dirty, onDirty])
  useEffect(() => {
    if (editing)
      root.current
        ?.querySelector('.award-editor h4')
        ?.focus({ preventScroll: true })
  }, [editing])
  useEffect(() => {
    if (!error || busy || !focusError.current) return
    focusError.current = false
    const target =
      root.current?.querySelector('[aria-invalid="true"]:not(:disabled)') ||
      root.current?.querySelector('.comp-error')
    target?.focus()
  }, [error, busy])

  function fieldError(path) {
    return errorsFor(error, path)?.replaceAll('Value error, ', '')
  }

  function start(event, award) {
    trigger.current = event.currentTarget
    const draft = award
      ? {
          kind: award.kind,
          units: award.units,
          grant_date: award.grant_date,
          grant_currency: award.grant_currency,
          exercise_price: award.exercise_price || '',
          valuation: award.valuation || '',
          valuation_date: award.valuation_date || '',
          last_year: award.last_year || '',
          vesting: award.vesting,
          allocations: award.allocations,
        }
      : {
          kind: 'rsu',
          units: '',
          grant_date: today(),
          grant_currency: data.currency_code,
          exercise_price: '',
          valuation: '',
          valuation_date: '',
          last_year: '',
          vesting: [],
          allocations: [],
        }
    setError(null)
    setMessage('')
    setEditor({
      id: award?.id,
      version: award?.version || 0,
      draft,
      baseline: JSON.stringify(draft),
    })
  }

  function change(patch) {
    setEditor((previous) => ({
      ...previous,
      draft: { ...previous.draft, ...patch },
    }))
    setError((previous) => {
      if (!previous?.fields?.length) return previous
      const changed = new Set(Object.keys(patch))
      if (changed.has('valuation') || changed.has('valuation_date')) {
        changed.add('valuation')
        changed.add('valuation_date')
      }
      if (changed.has('grant_date')) {
        for (const field of [
          'valuation_date',
          'last_year',
          'vesting',
          'allocations',
        ])
          changed.add(field)
      }
      if (changed.has('units')) changed.add('vesting')
      if (changed.has('last_year')) changed.add('allocations')
      const fields = previous.fields.filter(({ loc }) => !changed.has(loc[1]))
      return fields.length
        ? { ...previous, message: previous.message, fields }
        : null
    })
  }

  function changeRow(key, index, patch) {
    change({
      [key]: draft[key].map((row, position) =>
        position === index ? { ...row, ...patch } : row,
      ),
    })
  }
  function removeRow(key, index) {
    change({ [key]: draft[key].filter((_, position) => position !== index) })
  }

  function closeEditor() {
    setDiscard(false)
    setError(null)
    setEditor(null)
    requestAnimationFrame(() =>
      (trigger.current?.isConnected
        ? trigger.current
        : addButton.current
      )?.focus({ preventScroll: true }),
    )
  }

  async function mutate(operation, success) {
    if (guard.current) return
    guard.current = true
    setBusy(true)
    onBusy(true)
    setError(null)
    setMessage('')
    try {
      await operation()
      closeEditor()
      setMessage(success)
      report.retry()
    } catch (error) {
      focusError.current = true
      setError(error)
    } finally {
      guard.current = false
      setBusy(false)
      onBusy(false)
    }
  }

  function saveAward() {
    const body = {
      ...draft,
      expected_version: editor.version,
      package_currency: data.currency_code,
      exercise_price: draft.kind === 'option' ? draft.exercise_price : null,
      valuation: draft.valuation || null,
      valuation_date: draft.valuation_date || null,
      last_year: draft.last_year ? Number(draft.last_year) : null,
      allocations: draft.allocations.map((row) => ({
        ...row,
        year: Number(row.year),
      })),
    }
    return mutate(
      () =>
        api(`${path}/awards${editor.id ? `/${editor.id}` : ''}`, {
          method: editor.id ? 'PUT' : 'POST',
          body: JSON.stringify(body),
        }),
      'Equity award saved.',
    )
  }

  return (
    <section
      ref={root}
      className="equity-panel"
      aria-labelledby="equity-heading"
      onKeyDown={(event) => {
        if (event.key === 'Enter' && event.target.tagName === 'INPUT')
          event.preventDefault()
      }}
    >
      <div className="comp-section-heading">
        <div>
          <h3 id="equity-heading" tabIndex={-1}>
            <Gem size={17} aria-hidden="true" /> Equity and annual CTC
          </h3>
          <p>Record grants and their annual company cost.</p>
        </div>
      </div>
      <ErrorSummary error={report.error} />
      {report.error && (
        <button
          type="button"
          className="button secondary"
          onClick={report.retry}
        >
          Retry equity
        </button>
      )}
      {report.loading && (
        <p className="comp-status" role="status">
          {data ? 'Updating equity totals…' : 'Loading equity…'}
        </p>
      )}
      {message && (
        <p className="comp-success" role="status">
          {message}
        </p>
      )}
      {data && (
        <>
          <FormField
            id="equity-year"
            label="Calendar year"
            type="number"
            min="1900"
            max="9998"
            defaultValue={year}
            disabled={!!editor || busy}
            onBlur={(event) => {
              const value = Number(event.target.value)
              if (Number.isInteger(value) && value >= 1900 && value <= 9998)
                setYear(value)
              else event.target.value = year
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                event.currentTarget.blur()
              }
            }}
          />
          <dl
            className="equity-totals"
            aria-label={`Compensation totals for ${data.year}`}
          >
            {[
              ['Saved cash and benefits', data.guaranteed_cost],
              ['Annual equity cost', data.equity_cost],
              ['Guaranteed CTC', data.ctc],
              ['CTC with targets', data.target_ctc],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>
                  {value == null
                    ? 'Incomplete'
                    : money(value, data.currency_code)}
                </dd>
              </div>
            ))}
          </dl>
          {data.status === 'not_applicable' && (
            <p className="comp-muted">Equity marked not applicable.</p>
          )}
          {data.status === 'incomplete' && (
            <p className="comp-muted">
              {data.awards.length
                ? 'Check that every applicable award has an allocation in the package currency for this year.'
                : 'Add an equity award or mark equity as not applicable.'}
            </p>
          )}
          {!editor && (
            <>
              <ErrorSummary error={error} />
              {data.awards.map((award) => (
                <div className="equity-award" key={award.id}>
                  <div>
                    <strong>
                      {title(award.kind)} · {award.units} units
                    </strong>
                    <small>
                      Granted {award.grant_date} ·{' '}
                      {award.valuation == null
                        ? 'Unvalued'
                        : `${money(award.valuation, award.grant_currency)} as of ${award.valuation_date}`}
                    </small>
                    <small>
                      {award.unscheduled_units} units without a vesting date ·{' '}
                      {award.allocations.length} recorded years
                    </small>
                    <details>
                      <summary>Vesting and allocations</summary>
                      {award.exercise_price != null && (
                        <small>
                          Exercise price per unit: {award.grant_currency}{' '}
                          {award.exercise_price}
                        </small>
                      )}
                      {award.vesting.map((row) => (
                        <small key={row.date}>
                          {row.date} · {row.units} units
                        </small>
                      ))}
                      {award.allocations.map((row) => (
                        <small key={row.year}>
                          {row.year} allocation ·{' '}
                          {money(row.amount, row.currency_code)}
                        </small>
                      ))}
                      {award.last_year && (
                        <small>Final allocation year: {award.last_year}</small>
                      )}
                      {!award.vesting.length && !award.allocations.length && (
                        <small>
                          No vesting dates or annual allocations recorded.
                        </small>
                      )}
                    </details>
                  </div>
                  <button
                    type="button"
                    className="button secondary compact"
                    disabled={busy || report.loading}
                    onClick={(event) => start(event, award)}
                  >
                    Edit award
                  </button>
                </div>
              ))}
              <div className="comp-actions">
                <button
                  ref={addButton}
                  type="button"
                  className="button secondary"
                  disabled={busy || report.loading}
                  onClick={(event) => start(event)}
                >
                  <Plus size={16} aria-hidden="true" />
                  Add equity award
                </button>
                {!data.awards.length && data.status !== 'not_applicable' && (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={busy || report.loading}
                    onClick={() =>
                      mutate(
                        () => api(`${path}/not-applicable`, { method: 'PUT' }),
                        'Equity marked not applicable.',
                      )
                    }
                  >
                    Mark not applicable
                  </button>
                )}
              </div>
            </>
          )}
          {editor && (
            <fieldset disabled={busy} className="award-editor">
              <h4 tabIndex={-1}>
                {editor.id ? 'Edit equity award' : 'New equity award'}
              </h4>
              <ErrorSummary
                error={error}
                onReload={() => setDiscard('reload')}
              />
              <div className="award-fields">
                <SelectField
                  id="award-kind"
                  error={fieldError('kind')}
                  label="Award type"
                  value={draft.kind}
                  options={kinds}
                  disabled={busy}
                  onChange={(kind) => change({ kind, exercise_price: '' })}
                />
                <FormField
                  id="award-units"
                  error={fieldError('units')}
                  label="Units granted"
                  value={draft.units}
                  inputMode="decimal"
                  onChange={(event) => change({ units: event.target.value })}
                />
                <FormField
                  id="award-date"
                  error={fieldError('grant_date')}
                  label="Grant date"
                  type="date"
                  min="1900-01-01"
                  value={draft.grant_date}
                  max={today()}
                  onChange={(event) =>
                    change({ grant_date: event.target.value })
                  }
                />
                <SelectField
                  id="award-currency"
                  error={fieldError('grant_currency')}
                  label="Grant currency"
                  value={draft.grant_currency}
                  disabled={busy}
                  options={currencies.map((item) => ({
                    value: item.code,
                    label: item.code,
                  }))}
                  onChange={(grant_currency) => change({ grant_currency })}
                />
                {draft.kind === 'option' && (
                  <FormField
                    id="award-price"
                    error={fieldError('exercise_price')}
                    required
                    label={`Exercise price per unit (${draft.grant_currency})`}
                    inputMode="decimal"
                    value={draft.exercise_price}
                    onChange={(event) =>
                      change({ exercise_price: event.target.value })
                    }
                  />
                )}
                <FormField
                  id="award-value"
                  error={fieldError('valuation')}
                  required={!!draft.valuation_date}
                  label={`Grant valuation (${draft.grant_currency}, optional)`}
                  value={draft.valuation}
                  inputMode="decimal"
                  onChange={(event) =>
                    change({ valuation: event.target.value })
                  }
                />
                <FormField
                  id="award-valued"
                  error={fieldError('valuation_date')}
                  required={!!draft.valuation}
                  label="Valuation date"
                  type="date"
                  max={today()}
                  value={draft.valuation_date}
                  min={draft.grant_date || undefined}
                  hint={
                    draft.valuation
                      ? 'Required when a grant valuation is entered.'
                      : undefined
                  }
                  onChange={(event) =>
                    change({ valuation_date: event.target.value })
                  }
                />
                <FormField
                  id="award-last-year"
                  error={fieldError('last_year')}
                  label="Final allocation year (optional)"
                  type="number"
                  min="1900"
                  max="9998"
                  value={draft.last_year}
                  onChange={(event) =>
                    change({ last_year: event.target.value })
                  }
                />
              </div>
              <h4>Vesting schedule</h4>
              {draft.vesting.map((row, index) => (
                <div className="award-fields award-line" key={index}>
                  <FormField
                    id={`vest-date-${index}`}
                    error={fieldError(`vesting.${index}.date`)}
                    label={`Vesting date ${index + 1}`}
                    type="date"
                    value={row.date}
                    onChange={(event) =>
                      changeRow('vesting', index, { date: event.target.value })
                    }
                  />
                  <FormField
                    id={`vest-units-${index}`}
                    error={fieldError(`vesting.${index}.units`)}
                    label={`Vesting units ${index + 1}`}
                    value={row.units}
                    inputMode="decimal"
                    onChange={(event) =>
                      changeRow('vesting', index, { units: event.target.value })
                    }
                  />
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Remove vesting row ${index + 1}`}
                    onClick={() => removeRow('vesting', index)}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="button secondary compact"
                disabled={draft.vesting.length >= 120}
                onClick={() =>
                  change({
                    vesting: [...draft.vesting, { date: '', units: '' }],
                  })
                }
              >
                Add vesting date
              </button>
              <h4>Annual allocations</h4>
              <p className="comp-muted">
                Enter the cost to include each year. Use zero for a year with no
                cost.
              </p>
              {draft.allocations.map((row, index) => (
                <div className="award-fields award-line" key={index}>
                  <FormField
                    id={`allocation-year-${index}`}
                    error={fieldError(`allocations.${index}.year`)}
                    label={`Allocation year ${index + 1}`}
                    type="number"
                    min="1900"
                    max="9998"
                    value={row.year}
                    onChange={(event) =>
                      changeRow('allocations', index, {
                        year: event.target.value,
                      })
                    }
                  />
                  <FormField
                    id={`allocation-amount-${index}`}
                    error={
                      fieldError(`allocations.${index}.amount`) ||
                      fieldError(`allocations.${index}.currency_code`)
                    }
                    label={`Annual cost ${index + 1} (${row.currency_code})`}
                    value={row.amount}
                    disabled={row.currency_code !== data.currency_code}
                    inputMode="decimal"
                    onChange={(event) =>
                      changeRow('allocations', index, {
                        amount: event.target.value,
                      })
                    }
                  />
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Remove allocation ${index + 1}`}
                    onClick={() => removeRow('allocations', index)}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="button secondary compact"
                disabled={draft.allocations.length >= 60}
                onClick={() =>
                  change({
                    allocations: [
                      ...draft.allocations,
                      { year, amount: '', currency_code: data.currency_code },
                    ],
                  })
                }
              >
                Add annual allocation
              </button>
              <div className="comp-actions">
                <button
                  type="button"
                  className="button primary"
                  onClick={saveAward}
                >
                  {busy ? 'Saving…' : 'Save equity award'}
                </button>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => (dirty ? setDiscard('cancel') : closeEditor())}
                >
                  Cancel award edit
                </button>
              </div>
            </fieldset>
          )}
        </>
      )}
      <DiscardDialog
        open={!!discard}
        onCancel={() => setDiscard(false)}
        onDiscard={() => {
          if (discard === 'reload') report.retry()
          closeEditor()
        }}
      />
    </section>
  )
}
