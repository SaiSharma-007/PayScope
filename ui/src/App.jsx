import { useEffect, useRef } from 'react'
import {
  createBrowserRouter,
  RouterProvider,
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
import Overview from './features/workspace/Overview'
import SalaryInsights from './features/workspace/SalaryInsights'
import Rules from './features/compensation/Rules'
import RuleEditor from './features/compensation/RuleEditor'

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
      '/rules': 'Compensation rules',
    }
    document.title = `${titles[pathname] || (pathname.startsWith('/rules/') ? 'Compensation rule' : 'Page not found')} · PayScope`
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
      {!pathname.startsWith('/rules') &&
        !['/employees', '/overview', '/insights', '/activity'].includes(
          pathname,
        ) && <Header />}
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/sign-in" element={<SignIn />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<WorkspaceShell />}>
            <Route path="/employees" element={<Employees />} />
            <Route path="/overview" element={<Overview />} />
            <Route path="/insights" element={<SalaryInsights />} />
            <Route path="/activity" element={<WorkspacePreview />} />
            <Route path="/rules" element={<Rules />} />
            <Route path="/rules/new" element={<RuleEditor key="new-rule" />} />
            <Route path="/rules/:ruleId" element={<RuleEditor />} />
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

const router = createBrowserRouter([
  {
    path: '*',
    element: (
      <AuthProvider>
        <Pages />
      </AuthProvider>
    ),
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
