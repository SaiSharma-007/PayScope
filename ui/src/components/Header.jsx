import { Link } from 'react-router-dom'
import { useAuth } from '../features/auth/useAuth'
import Brand from './Brand'
import ThemeSwitch from './ThemeSwitch'
import SignOutButton from './SignOutButton'

export default function Header() {
  const auth = useAuth()
  return (
    <header className="site-header page">
      <Brand />
      <nav aria-label="Main navigation" className="header-nav">
        {auth.session ? (
          <Link className="nav-link" to="/employees">
            Employees
          </Link>
        ) : (
          <a className="nav-link" href="/#overview">
            How it works
          </a>
        )}
        <ThemeSwitch />
        {auth.session ? (
          <SignOutButton />
        ) : (
          <Link className="button secondary compact" to="/sign-in">
            Sign in
          </Link>
        )}
      </nav>
    </header>
  )
}
