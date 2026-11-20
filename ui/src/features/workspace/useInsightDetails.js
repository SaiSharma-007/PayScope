import { useEffect, useId, useRef, useState } from 'react'

export function useInsightDetails() {
  const [entry, setEntry] = useState(null)
  const id = useId()
  const timer = useRef()
  const cancelClose = () => clearTimeout(timer.current)
  useEffect(() => () => clearTimeout(timer.current), [])

  function preview(key, event) {
    const anchor = event.currentTarget
    const x =
      event.type === 'pointerenter'
        ? event.clientX - anchor.getBoundingClientRect().left
        : null
    cancelClose()
    setEntry((previous) => (previous?.pinned ? previous : { key, anchor, x }))
  }

  function leave() {
    cancelClose()
    timer.current = setTimeout(
      () => setEntry((previous) => (previous?.pinned ? previous : null)),
      100,
    )
  }

  function pin(key, event) {
    const anchor = event.currentTarget
    const x = event.detail
      ? event.clientX - anchor.getBoundingClientRect().left
      : null
    cancelClose()
    setEntry((previous) =>
      previous?.pinned && previous.key === key
        ? null
        : { key, anchor, x, pinned: true },
    )
  }

  function dismiss(restore = false) {
    cancelClose()
    if (restore && entry?.pinned) entry.anchor.focus({ preventScroll: true })
    setEntry(null)
  }

  function trigger(key) {
    const active = entry?.key === key
    return {
      'aria-describedby': active && !entry.pinned ? id : undefined,
      'aria-controls': active && entry.pinned ? id : undefined,
      'aria-expanded': Boolean(active && entry.pinned),
      onPointerEnter: (event) => {
        if (event.pointerType === 'mouse') preview(key, event)
      },
      onPointerLeave: leave,
      onFocus: (event) => {
        if (event.currentTarget.matches(':focus-visible')) preview(key, event)
      },
      onBlur: leave,
    }
  }

  return { entry, id, trigger, pin, dismiss, leave, cancelClose }
}
