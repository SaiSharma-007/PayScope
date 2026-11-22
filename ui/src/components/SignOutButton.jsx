import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { Button } from './ui/button'
import { useAuth } from '../features/auth/useAuth'

export default function SignOutButton() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function logout() {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await auth.signOut()
      navigate('/sign-in', { replace: true })
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="sign-out">
      <Button
        variant="secondary"
        className="sign-out-control"
        type="button"
        title="Sign out"
        onClick={logout}
        disabled={busy}
      >
        <LogOut data-icon="inline-start" aria-hidden="true" />
        <span>{busy ? 'Signing out…' : 'Sign out'}</span>
      </Button>
      {error && (
        <p className="sign-out-error error-message" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
