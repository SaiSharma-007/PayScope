import { useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { Moon, Sun } from 'lucide-react'
import { Switch } from './ui/switch'

export default function ThemeSwitch({ compact = false }) {
  const [dark, setDark] = useState(
    () => document.documentElement.dataset.theme === 'dark',
  )
  const desiredTheme = useRef(dark)
  const transition = useRef(null)
  const fallbackTimer = useRef(null)
  function applyTheme() {
    document.documentElement.setAttribute('data-theme', desiredTheme.current ? 'dark' : 'light')
    setDark(desiredTheme.current)
  }
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    function followSystem(event) {
      let saved
      try {
        saved = localStorage.getItem('payscope.theme')
      } catch {
        /* System theme remains available without storage. */
      }
      if (!saved) {
        desiredTheme.current = event.matches
        setDark(event.matches)
        document.documentElement.setAttribute('data-theme', event.matches ? 'dark' : 'light')
      }
    }
    media.addEventListener('change', followSystem)
    return () => {
      media.removeEventListener('change', followSystem)
      transition.current?.skipTransition()
      clearTimeout(fallbackTimer.current)
      document.documentElement.classList.remove('theme-changing')
    }
  }, [])
  function toggle(event) {
    desiredTheme.current = !desiredTheme.current
    const next = desiredTheme.current
    const reducedMotion =
      event.detail === 0 ||
      matchMedia('(prefers-reduced-motion: reduce)').matches
    if (transition.current) {
      transition.current.skipTransition()
      flushSync(applyTheme)
    } else if (!reducedMotion && document.startViewTransition) {
      const active = document.startViewTransition(() => flushSync(applyTheme))
      transition.current = active
      active.ready.catch(() => {})
      active.finished.finally(() => {
        if (transition.current === active) transition.current = null
      })
    } else {
      if (!reducedMotion) {
        document.documentElement.classList.add('theme-changing')
        clearTimeout(fallbackTimer.current)
        fallbackTimer.current = setTimeout(() => {
          document.documentElement.classList.remove('theme-changing')
        }, 240)
      }
      applyTheme()
    }
    try {
      localStorage.setItem('payscope.theme', next ? 'dark' : 'light')
    } catch {
      /* Theme works for this visit. */
    }
  }
  if (compact) return <Switch aria-label="Dark theme" checked={dark} onClick={toggle} />

  return (
    <button
      className="theme-switch"
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label="Dark theme"
      onClick={toggle}
    >
      <Sun size={16} aria-hidden="true" />
      <Moon size={16} aria-hidden="true" />
      <span className="theme-thumb" />
    </button>
  )
}
