import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Eye, EyeOff, Moon } from 'lucide-react'
import Brand from '@/components/Brand'
import ThemeSwitch from '@/components/ThemeSwitch'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardContent, CardDescription } from '@/components/ui/card'
import { Field, FieldGroup, FieldLabel, FieldError } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { InputGroup, InputGroupInput, InputGroupAddon, InputGroupButton } from '@/components/ui/input-group'
import { Spinner } from '@/components/ui/spinner'
import './sign-in.css'
import { useAuth } from './useAuth'

export default function SignIn() {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState({})
  const [retryMessage, setRetryMessage] = useState('')
  const emailRef = useRef(null)
  const passwordRef = useRef(null)
  const submitting = useRef(false)
  if (auth.session) return <Navigate to="/overview" replace />

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
    if (Object.keys(next).length) {
      ;(next.email ? emailRef : passwordRef).current.focus()
      return
    }
    toast.dismiss('sign-in-error')
    setRetryMessage('')
    submitting.current = true
    setBusy(true)
    try {
      await auth.signIn(email, password)
      navigate('/overview', { replace: true })
    } catch (error) {
      const message = error.status === 401
        ? { title: 'Email or password is incorrect', description: 'Check both fields and try again.' }
        : error.status === 429
          ? { title: 'Too many attempts', description: 'Wait a moment before trying to sign in again.' }
          : error.status === 0
            ? { title: 'Could not connect', description: 'Check your connection and try again.' }
            : error.status >= 500
              ? { title: 'Sign-in is temporarily unavailable', description: 'Try again shortly.' }
              : { title: 'Could not sign in', description: 'Please try again.' }
      setRetryMessage(`${message.title}. ${message.description}`)
      toast.error(message.title, { id: 'sign-in-error', description: message.description })
    } finally {
      submitting.current = false
      setBusy(false)
    }
  }

  return (
    <div className="payscope-signin">
      <header className="signin-header">
        <Brand />
        <label className="signin-theme-toggle">
          <Moon size={16} aria-hidden="true" />
          <span>Dark theme</span>
          <ThemeSwitch compact />
        </label>
      </header>
      <main id="main" className="signin-main">
        <Card className="signin-card">
          <CardHeader>
            <h1>Sign in to PayScope</h1>
            <CardDescription>Open your HR workspace to manage salaries and review compensation.</CardDescription>
          </CardHeader>
          <CardContent>
            {location.state?.expired && (
              <Alert role="status"><AlertDescription>Sign in to continue to your workspace.</AlertDescription></Alert>
            )}
            <form onSubmit={submit} noValidate aria-busy={busy}>
              <FieldGroup>
                <Field data-invalid={Boolean(errors.email)} data-disabled={busy}>
                  <FieldLabel htmlFor="email">Email address</FieldLabel>
                  <Input ref={emailRef} id="email" name="email" type="email" autoComplete="username"
                    defaultValue="hr@payscope.example" aria-invalid={Boolean(errors.email)}
                    aria-describedby={errors.email ? 'email-error' : undefined} disabled={busy} />
                  {errors.email && <FieldError id="email-error">{errors.email}</FieldError>}
                </Field>
                <Field data-invalid={Boolean(errors.password)} data-disabled={busy}>
                  <FieldLabel htmlFor="password">Password</FieldLabel>
                  <InputGroup>
                    <InputGroupInput ref={passwordRef} id="password" name="password"
                      type={visible ? 'text' : 'password'} autoComplete="current-password"
                      aria-invalid={Boolean(errors.password)}
                      aria-describedby={errors.password ? 'password-error' : undefined} disabled={busy} />
                    <InputGroupAddon align="inline-end">
                      <InputGroupButton type="button" size="icon-sm" disabled={busy}
                        onClick={() => setVisible(value => !value)}
                        aria-label={visible ? 'Hide password' : 'Show password'}>
                        {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                      </InputGroupButton>
                    </InputGroupAddon>
                  </InputGroup>
                  {errors.password && <FieldError id="password-error">{errors.password}</FieldError>}
                </Field>
                <Button type="submit" disabled={busy} data-signin-action=""
                  aria-describedby={retryMessage ? 'signin-retry' : undefined}>
                  {busy ? 'Signing in…' : 'Sign in'}
                  {busy ? <Spinner data-icon="inline-end" aria-hidden="true" /> : <ArrowRight data-icon="inline-end" aria-hidden="true" />}
                </Button>
                {retryMessage && <p id="signin-retry" className="signin-retry">{retryMessage}</p>}
              </FieldGroup>
            </form>
            <p className="signin-demo-note">This workspace contains fictional employee data.</p>
          </CardContent>
        </Card>
        <Button asChild variant="link">
          <Link to="/"><ArrowLeft data-icon="inline-start" /> Back to PayScope</Link>
        </Button>
      </main>
    </div>
  )
}
