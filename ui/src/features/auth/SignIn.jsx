import { useRef, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, LockKeyhole } from 'lucide-react'
import { useAuth } from './useAuth'

export default function SignIn() {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState({})
  const [failure, setFailure] = useState('')
  const emailRef = useRef(null)
  const passwordRef = useRef(null)
  const errorRef = useRef(null)
  const submitting = useRef(false)
  if (auth.session) return <Navigate to="/employees" replace />

  async function submit(event) {
    event.preventDefault()
    if (submitting.current) return
    const form = new FormData(event.currentTarget)
    const email = form.get('email').trim()
    const password = form.get('password')
    const next = {}
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      next.email = 'Enter a valid email address.'
    if (!password) next.password = 'Enter your password.'
    setErrors(next)
    setFailure('')
    if (Object.keys(next).length) {
      ;(next.email ? emailRef : passwordRef).current.focus()
      return
    }
    submitting.current = true
    setBusy(true)
    try {
      await auth.signIn(email, password)
      navigate('/employees', { replace: true })
    } catch (error) {
      setFailure(
        error.status === 401
          ? 'That email and password didn’t match. Please try again.'
          : error.message,
      )
      window.requestAnimationFrame(() => errorRef.current?.focus())
    } finally {
      submitting.current = false
      setBusy(false)
    }
  }

  return (
    <main id="main" className="page auth-page">
      <section className="auth-intro">
        <span className="eyebrow">YOUR HR WORKSPACE</span>
        <h1>
          A clearer picture.
          <br />
          <span>A calmer day.</span>
        </h1>
        <p>
          Your people and their pay,
          <br />
          with room to see what matters.
        </p>
        <div className="auth-illustration" aria-hidden="true">
          <div className="orbital-wash">
            <span />
          </div>
          <div className="auth-example panel">
            <div className="example-person">
              <span className="avatar">AR</span>
              <span>
                <strong>Ananya Rao</strong>
                <small>Software Engineer · India</small>
              </span>
            </div>
            <hr />
            <span className="small-label">Annual gross base salary</span>
            <strong className="example-salary">INR 1,450,000.00</strong>
            <span className="example-note">
              A fictional record, in perspective.
            </span>
          </div>
        </div>
      </section>
      <section className="panel sign-in-panel" aria-labelledby="signin-title">
        <span className="icon-tile">
          <LockKeyhole size={22} aria-hidden="true" />
        </span>
        <h2 id="signin-title">Welcome back.</h2>
        <p>Sign in to your HR workspace.</p>
        {location.state?.expired && (
          <p className="notice" role="status">
            Sign in to continue to Employees.
          </p>
        )}
        <form onSubmit={submit} noValidate aria-busy={busy}>
          {failure && (
            <div
              className="error-banner"
              role="alert"
              tabIndex={-1}
              ref={errorRef}
            >
              {failure}
            </div>
          )}
          <div className="field">
            <label htmlFor="email">Email address</label>
            <input
              ref={emailRef}
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              defaultValue="hr@payscope.example"
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email ? 'email-error' : undefined}
              disabled={busy}
            />
            {errors.email && (
              <p id="email-error" className="error-message">
                {errors.email}
              </p>
            )}
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <div className="password-field">
              <input
                ref={passwordRef}
                id="password"
                name="password"
                type={visible ? 'text' : 'password'}
                autoComplete="current-password"
                aria-invalid={Boolean(errors.password)}
                aria-describedby={
                  errors.password ? 'password-error' : undefined
                }
                disabled={busy}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setVisible(!visible)}
                aria-label={visible ? 'Hide password' : 'Show password'}
                aria-pressed={visible}
              >
                {visible ? (
                  <EyeOff size={19} aria-hidden="true" />
                ) : (
                  <Eye size={19} aria-hidden="true" />
                )}
              </button>
            </div>
            {errors.password && (
              <p id="password-error" className="error-message">
                {errors.password}
              </p>
            )}
          </div>
          <button
            className="button primary submit-button"
            type="submit"
            disabled={busy}
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="demo-note">
          This workspace contains fictional employee data.
        </p>
        <Link className="text-link return-link" to="/">
          Back to PayScope
        </Link>
      </section>
    </main>
  )
}
