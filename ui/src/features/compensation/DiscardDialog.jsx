import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'

export function DiscardDialog({ open, onCancel, onDiscard }) {
  const dialog = useRef(null)
  const titleId = useId()
  useEffect(() => {
    if (open && !dialog.current.open) dialog.current.showModal()
    if (!open && dialog.current.open) dialog.current.close()
  }, [open])
  return createPortal(
    <dialog
      ref={dialog}
      className="discard-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault()
        onCancel()
      }}
    >
      <h2 id={titleId}>Discard unsaved changes?</h2>
      <p>Your saved compensation stays unchanged.</p>
      <div className="comp-actions">
        <button
          className="button secondary"
          type="button"
          autoFocus
          onClick={onCancel}
        >
          Keep editing
        </button>
        <button className="button primary" type="button" onClick={onDiscard}>
          Discard changes
        </button>
      </div>
    </dialog>,
    document.body,
  )
}
