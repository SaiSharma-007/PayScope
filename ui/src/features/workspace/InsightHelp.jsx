import { Info, X } from 'lucide-react'
import { useLayoutEffect, useRef } from 'react'
import { useInsightDetails } from './useInsightDetails'

export function InsightCard({ details, label, children, as: Element = 'div' }) {
  const card = useRef(null)
  const dismiss = useRef(null)
  const { entry, id } = details
  useLayoutEffect(() => {
    dismiss.current = details.dismiss
  })

  useLayoutEffect(() => {
    if (!entry) return
    const { anchor, x, pinned } = entry
    const element = card.current
    element.showPopover()
    if (pinned) element.focus({ preventScroll: true })

    function place() {
      const bounds = anchor.getBoundingClientRect()
      const viewport = window.visualViewport
      const left = viewport?.offsetLeft ?? 0
      const top = viewport?.offsetTop ?? 0
      const right = left + (viewport?.width ?? window.innerWidth)
      const bottom = top + (viewport?.height ?? window.innerHeight)
      const scrollport = anchor
        .closest('.insight-timeline-scroll')
        ?.getBoundingClientRect()
      const visibleLeft = Math.max(left, bounds.left, scrollport?.left ?? left)
      const visibleRight = Math.min(
        right,
        bounds.right,
        scrollport?.right ?? right,
      )
      if (
        bounds.bottom < top ||
        bounds.top > bottom ||
        visibleRight <= visibleLeft
      ) {
        dismiss.current()
        return
      }
      const gutter = 10
      element.style.maxWidth = `${right - left - gutter * 2}px`
      element.style.maxHeight = `${bottom - top - gutter * 2}px`
      const { width, height } = element.getBoundingClientRect()
      const center = Math.min(
        visibleRight,
        Math.max(visibleLeft, bounds.left + (x ?? bounds.width / 2)),
      )
      const below = bounds.bottom + 6
      const above = bounds.top - height - 6
      const y =
        height <= bottom - below || bounds.top - top < bottom - bounds.bottom
          ? below
          : above
      element.style.left = `${Math.max(left + gutter, Math.min(center - width / 2, right - width - gutter))}px`
      element.style.top = `${Math.max(top + gutter, Math.min(y, bottom - height - gutter))}px`
    }

    function outside(event) {
      if (!element.contains(event.target) && !anchor.contains(event.target))
        dismiss.current()
    }
    function escape(event) {
      if (event.key !== 'Escape') return
      event.preventDefault()
      event.stopPropagation()
      dismiss.current(true)
    }

    place()
    const resize = new ResizeObserver(place)
    resize.observe(element)
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    window.visualViewport?.addEventListener('resize', place)
    window.visualViewport?.addEventListener('scroll', place)
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape, true)
    return () => {
      element.hidePopover()
      resize.disconnect()
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
      window.visualViewport?.removeEventListener('resize', place)
      window.visualViewport?.removeEventListener('scroll', place)
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape, true)
    }
  }, [entry])

  if (!entry) return null
  return (
    <Element
      className="insight-float"
      ref={card}
      id={id}
      popover="manual"
      role={entry.pinned ? 'region' : 'tooltip'}
      aria-label={label}
      tabIndex={entry.pinned ? -1 : undefined}
      onPointerEnter={details.cancelClose}
      onPointerLeave={details.leave}
    >
      {entry.pinned && (
        <button
          type="button"
          className="insight-float-close"
          aria-label="Close details"
          onClick={() => details.dismiss(true)}
        >
          <X size={15} aria-hidden="true" />
        </button>
      )}
      {children}
    </Element>
  )
}

export function InsightHelp({ label, children }) {
  const details = useInsightDetails({ definition: true })
  if (!children) return null
  return (
    <>
      <button
        type="button"
        className="insight-help"
        aria-label={`About ${label}`}
        {...details.trigger(label)}
        onClick={(event) => details.pin(label, event)}
      >
        <Info size={15} aria-hidden="true" />
      </button>
      <InsightCard details={details} label={`About ${label}`} as="span">
        <strong>{label}</strong>
        <span className="insight-help-copy">{children}</span>
      </InsightCard>
    </>
  )
}
