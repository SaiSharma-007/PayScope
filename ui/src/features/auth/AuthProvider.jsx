import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { request } from '../../lib/http'
import { AuthContext } from './context'

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: 'loading', session: null })
  const [attempt, setAttempt] = useState(0)
  const generation = useRef(0)
  // A new authentication session must never inherit another session's salary chats.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const sessionCache = useMemo(() => new Map(), [state.session])
  useEffect(() => {
    const controller = new AbortController()
    const current = ++generation.current
    request('/auth/session', { signal: controller.signal })
      .then((session) => {
        if (generation.current === current)
          setState({ status: 'ready', session })
      })
      .catch((error) => {
        if (error.name === 'AbortError') return
        if (generation.current === current)
          setState({
            status: error.status === 401 ? 'ready' : 'error',
            session: null,
          })
      })
    return () => controller.abort()
  }, [attempt])

  useEffect(() => {
    if (!state.session) return
    const remaining = new Date(state.session.expires_at).getTime() - Date.now()
    const timer = window.setTimeout(
      () => setState({ status: 'ready', session: null }),
      Math.max(0, remaining),
    )
    return () => window.clearTimeout(timer)
  }, [state.session])

  async function signIn(email, password) {
    const session = await request('/auth/sign-in', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    generation.current++
    setState({ status: 'ready', session })
  }

  async function signOut() {
    try {
      await request('/auth/sign-out', {
        method: 'POST',
        csrf: state.session.csrf_token,
      })
    } catch (error) {
      if (error.status !== 401) throw error
    }
    generation.current++
    setState({ status: 'ready', session: null })
  }

  const expire = useCallback(() => {
    generation.current++
    setState({ status: 'ready', session: null })
  }, [])

  function retrySession() {
    setState({ status: 'loading', session: null })
    setAttempt((previous) => previous + 1)
  }

  return (
    <AuthContext
      value={{ ...state, sessionCache, refresh: retrySession, signIn, signOut, expire }}
    >
      {children}
    </AuthContext>
  )
}
