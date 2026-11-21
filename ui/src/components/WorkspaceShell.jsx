import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Activity,
  ArrowUpRight,
  ChartNoAxesCombined,
  FileChartColumn,
  ChevronRight,
  LayoutDashboard,
  PanelLeft,
  Settings2,
  SlidersHorizontal,
  Users,
  X,
} from 'lucide-react'
import { useAuth } from '../features/auth/useAuth'
import Brand from './Brand'
import ThemeSwitch from './ThemeSwitch'
import SignOutButton from './SignOutButton'

const pages = [
  {
    path: '/overview',
    label: 'Overview',
    icon: LayoutDashboard,
  },
  { path: '/employees', label: 'Employees', icon: Users },
  { path: '/rules', label: 'Compensation rules', icon: SlidersHorizontal },
  {
    path: '/insights',
    label: 'Salary insights',
    icon: ChartNoAxesCombined,
  },
  { path: '/saved-reports', label: 'Saved reports', icon: FileChartColumn },
  { path: '/activity', label: 'Activity', icon: Activity, preview: true },
]

function Navigation({ onNavigate }) {
  const { session } = useAuth()
  return (
    <>
      <div className="workspace-brand">
        <Brand />
      </div>
      <div className="workspace-team">
        <span className="team-mark">P</span>
        <span className="nav-copy">
          <strong>People workspace</strong>
          <small>Demo organization</small>
        </span>
      </div>
      <nav aria-label="Workspace navigation" className="workspace-nav">
        <p className="nav-section-label">WORKSPACE</p>
        {pages.map(({ path, label, icon: Icon, preview }) => (
          <NavLink
            key={path}
            to={path}
            onClick={onNavigate}
            aria-label={label}
            title={label}
            className={({ isActive }) =>
              `workspace-link${isActive ? ' active' : ''}`
            }
          >
            <Icon size={20} aria-hidden="true" />
            <span className="nav-copy">{label}</span>
            {preview && (
              <span className="nav-preview" aria-hidden="true">
                Preview
              </span>
            )}
          </NavLink>
        ))}
        <p className="nav-section-label nav-secondary">MANAGE</p>
        <span className="workspace-link nav-unavailable" aria-disabled="true">
          <Settings2 size={20} aria-hidden="true" />
          <span className="nav-copy">Settings</span>
          <span className="nav-preview">Soon</span>
        </span>
        {session?.user.manage_agent_prompts && (
          <>
            <p className="nav-section-label nav-secondary">ADMIN</p>
            <NavLink
              to="/admin/agent-prompts"
              onClick={onNavigate}
              title="Prompt catalog"
              aria-label="Prompt catalog"
              className={({ isActive }) =>
                `workspace-link${isActive ? ' active' : ''}`
              }
            >
              <SlidersHorizontal size={20} aria-hidden="true" />
              <span className="nav-copy">Prompt catalog</span>
            </NavLink>
          </>
        )}
        {session?.user.view_agent_observability && <NavLink to="/admin/agent-runs" onClick={onNavigate} title="Agent observability" className={({isActive})=>`workspace-link${isActive?' active':''}`}><Activity size={20} aria-hidden="true"/><span className="nav-copy">Agent observability</span></NavLink>}
      </nav>
      <div className="sidebar-bottom">
        <Link
          to="/"
          onClick={onNavigate}
          className="workspace-link"
          aria-label="About PayScope"
          title="About PayScope"
        >
          <ArrowUpRight size={19} aria-hidden="true" />
          <span className="nav-copy">About PayScope</span>
        </Link>
      </div>
    </>
  )
}

export default function WorkspaceShell() {
  const { pathname } = useLocation()
  const { session } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const [mobile, setMobile] = useState(
    () => matchMedia('(max-width: 1100px)').matches,
  )
  const [drawerOpen, setDrawerOpen] = useState(false)
  const drawer = useRef(null)
  useEffect(() => {
    const media = matchMedia('(max-width: 1100px)')
    function resize(event) {
      setMobile(event.matches)
      if (!event.matches) drawer.current.close()
    }
    media.addEventListener('change', resize)
    return () => media.removeEventListener('change', resize)
  }, [])
  const title =
    pages.find(
      (page) => page.path === pathname || pathname.startsWith(page.path + '/'),
    )?.label ||
    (pathname === '/admin/agent-prompts' ? 'Prompt catalog' : pathname.startsWith('/admin/agent-runs') ? 'Agent observability' : 'Workspace')
  function toggleNavigation(event) {
    if (mobile) {
      drawer.current.dataset.keyboard = String(event.detail === 0)
      drawer.current.showModal()
      setDrawerOpen(true)
    } else setCollapsed((previous) => !previous)
  }
  return (
    <div className={`workspace-shell${collapsed ? ' sidebar-collapsed' : ''}`}>
      <aside className="workspace-sidebar">
        <Navigation />
      </aside>
      <dialog
        id="workspace-navigation"
        className="navigation-drawer"
        ref={drawer}
        aria-label="Workspace navigation"
        onClose={() => setDrawerOpen(false)}
        onClick={(event) => {
          if (event.target === event.currentTarget) drawer.current.close()
        }}
      >
        <button
          className="icon-button drawer-close"
          aria-label="Close navigation"
          autoFocus
          onClick={() => drawer.current.close()}
        >
          <X size={20} />
        </button>
        <Navigation onNavigate={() => drawer.current.close()} />
      </dialog>
      <div className="workspace-body">
        <header className="workspace-topbar">
          <div className="topbar-location">
            <button
              className="icon-button"
              aria-label="Toggle navigation"
              title="Toggle navigation"
              aria-expanded={mobile ? drawerOpen : !collapsed}
              aria-controls={mobile ? 'workspace-navigation' : undefined}
              onClick={toggleNavigation}
            >
              <PanelLeft size={21} aria-hidden="true" />
            </button>
            <nav aria-label="Breadcrumb">
              <span>Workspace</span>
              <ChevronRight size={14} aria-hidden="true" />
              <strong aria-current="page">{title}</strong>

      </nav>
          </div>
          <div className="topbar-actions">
            <span className="workspace-environment">Demo workspace</span>
            <ThemeSwitch />
            <span className="topbar-account">
              <span className="avatar" aria-hidden="true">
                HR
              </span>
              <span>
                <strong>{session.user.display_name}</strong>
                <small>HR manager</small>
              </span>
            </span>
            <SignOutButton />
          </div>
        </header>
        <Outlet />
      </div>
    </div>
  )
}
