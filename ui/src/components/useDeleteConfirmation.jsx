import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { CalendarDays, Coins, FileChartColumn, Layers, MessageSquare } from 'lucide-react'
import './delete-confirmation.css'

const icons = { chat: MessageSquare, report: FileChartColumn, component: Layers, vesting: CalendarDays, allocation: Coins }

export function useDeleteConfirmation() {
  const [pending, setPending] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const dialog = useRef(null)
  const origin = useRef(null)
  const running = useRef(false)
  const label = useId()
  useEffect(() => {
    if (pending && !dialog.current.open) dialog.current.showModal()
    if (!pending && dialog.current.open) {
      dialog.current.close()
      const target = origin.current?.isConnected ? origin.current : document.querySelector('main h1')
      target?.focus({ preventScroll: true })
    }
  }, [pending])
  function confirm(options, action) {
    if (running.current) return
    origin.current = document.activeElement
    setError('')
    setPending({ ...options, action })
  }
  function cancel() {
    if (!running.current) setPending(null)
  }
  const Icon = icons[pending?.kind] || Layers
  const confirmation = createPortal(
    <dialog ref={dialog} role="alertdialog" className="delete-confirmation" data-kind={pending?.kind}
      aria-labelledby={`${label}-title`} aria-describedby={`${label}-description`}
      aria-busy={busy || undefined}
      onCancel={(event) => { event.preventDefault(); event.stopPropagation(); cancel() }}>
      <div className="delete-confirmation-icon"><Icon size={23} aria-hidden="true" /></div>
      <h2 id={`${label}-title`}>{pending?.title}</h2>
      <p id={`${label}-description`}>{pending?.description}</p>
      <div className="delete-confirmation-object">{pending?.name}</div>
      {pending?.note && <p className="delete-confirmation-note">{pending.note}</p>}
      {error && <p className="delete-confirmation-error" role="alert">{error}</p>}
      <div className="delete-confirmation-actions">
        <button type="button" className="button secondary" autoFocus disabled={busy} onClick={cancel}>Cancel</button>
        <button type="button" className="button delete-confirmation-submit" disabled={busy} onClick={async () => {
          if (running.current || !pending) return
          running.current = true; setBusy(true); setError('')
          try {
            const result = await pending.action()
            if (result === false) throw new Error('The item could not be removed. Please try again.')
            setPending(null)
          } catch (problem) { setError(problem.message || 'The item could not be removed. Please try again.') }
          finally { running.current = false; setBusy(false) }
        }}>{busy ? 'Removing…' : pending?.actionLabel}</button>
      </div>
    </dialog>, document.body,
  )
  return { confirm, confirmation }
}
