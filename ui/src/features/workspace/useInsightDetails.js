import { useEffect, useId, useRef, useState } from 'react'

let openCard

export function useInsightDetails({ definition = false } = {}) {
  const [entry, setEntry] = useState(null)
  const id = useId()
  const timer = useRef()
  const cancelClose = () => clearTimeout(timer.current)
  useEffect(
    () => () => {
      clearTimeout(timer.current)
      if (openCard?.id === id) openCard = undefined
    },
    [id],
  )

  function close() {
    cancelClose()
    if (openCard?.id === id) openCard = undefined
    setEntry(null)
  }

  function claim(pinned) {
    const switchingDefinition =
      definition && openCard?.definition && openCard.id !== id
    if (!pinned && openCard?.pinned && !switchingDefinition) return false
    if (openCard?.id !== id) openCard?.close()
    openCard = { id, definition, pinned, close }
    return true
  }

  function preview(key, event) {
    if (!claim(false)) return
    const anchor = event.currentTarget
    const x =
      event.type === 'pointerenter'
        ? event.clientX - anchor.getBoundingClientRect().left
        : null
    cancelClose()
    setEntry({ key, anchor, x })
  }

  function leave() {
    cancelClose()
    timer.current = setTimeout(() => {
      if (openCard?.id === id && !openCard.pinned) close()
    }, 100)
  }

  function pin(key, event) {
    const anchor = event.currentTarget
    const x = event.detail
      ? event.clientX - anchor.getBoundingClientRect().left
      : null
    if (entry?.pinned && entry.key === key) {
      close()
      return
    }
    claim(true)
    cancelClose()
    setEntry({ key, anchor, x, pinned: true })
  }

  function dismiss(restore = false) {
    if (restore && entry?.pinned) entry.anchor.focus({ preventScroll: true })
    close()
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
