import { useEffect, useRef } from 'react'
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { AuthProvider } from './features/auth/AuthProvider'
import { useAuth } from './features/auth/useAuth'
import Landing from './features/landing/Landing'
import SignIn from './features/auth/SignIn'
import Employees from './features/employees/Employees'
import Header from './components/Header'
import Feedback from './components/Feedback'
import WorkspaceShell from './components/WorkspaceShell'
import WorkspacePreview from './features/workspace/WorkspacePreview'

function ProtectedRoute() {
  const auth = useAuth()
  if (auth.status === 'loading')
    return <Feedback message="Opening your workspace…" />
  if (auth.status === 'error')
    return (
      <Feedback
        message="Your session could not be checked."
        onRetry={auth.refresh}
      />
    )
  return auth.session ? (
    <Outlet />
  ) : (
    <Navigate to="/sign-in" replace state={{ expired: true }} />
  )
}

function Pages() {
  const { pathname } = useLocation()
  const previousPath = useRef(pathname)
  useEffect(() => {
    const titles = {
      '/': 'Employee salary management',
      '/sign-in': 'Sign in',
      '/employees': 'Employees',
      '/overview': 'Overview',
      '/insights': 'Salary insights',
      '/activity': 'Activity',
    }
    document.title = `${titles[pathname] || 'Page not found'} · PayScope`
    window.scrollTo(0, 0)
    if (previousPath.current !== pathname) {
      const heading = document.querySelector('main h1')
      heading?.setAttribute('tabindex', '-1')
      heading?.focus({ preventScroll: true })
      previousPath.current = pathname
    }
  }, [pathname])
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {!['/employees', '/overview', '/insights', '/activity'].includes(
        pathname,
      ) && <Header />}
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/sign-in" element={<SignIn />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<WorkspaceShell />}>
            <Route path="/employees" element={<Employees />} />
            <Route path="/overview" element={<WorkspacePreview />} />
            <Route path="/insights" element={<WorkspacePreview />} />
            <Route path="/activity" element={<WorkspacePreview />} />
          </Route>
        </Route>
        <Route
          path="*"
          element={
            <main id="main" className="page not-found">
              <span className="eyebrow">404</span>
              <h1>That page isn’t here.</h1>
              <a className="button primary" href="/">
                Return to PayScope
              </a>
            </main>
          }
        />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Pages />
      </AuthProvider>
    </BrowserRouter>
  )
}
