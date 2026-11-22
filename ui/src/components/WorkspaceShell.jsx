import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Activity,
  ArrowUpRight,
  ChartNoAxesCombined,
  FileChartColumn,
  ChevronRight,
  House,
  Layers,
  PanelLeft,
  SlidersHorizontal,
  Users,
} from 'lucide-react'
import { useAuth } from '../features/auth/useAuth'
import { Button } from './ui/button'
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from './ui/sheet'
import Brand from './Brand'
import ThemeSwitch from './ThemeSwitch'
import SignOutButton from './SignOutButton'

const pages = [
  {
    path: '/overview',
    label: 'Overview',
    icon: House,
  },
  { path: '/employees', label: 'Employees', icon: Users },
  { path: '/rules', label: 'Compensation rules', icon: Layers },
  {
    path: '/insights',
    label: 'Salary insights',
    icon: ChartNoAxesCombined,
  },
  { path: '/saved-reports', label: 'Saved reports', icon: FileChartColumn },
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
        {pages.map(({ path, label, icon: Icon }) => (
          <Button key={path} asChild variant="ghost" className="workspace-link">
            <NavLink
              to={path}
              onClick={onNavigate}
              aria-label={label}
              title={label}
            >
              <Icon aria-hidden="true" />
              <span className="nav-copy">{label}</span>
            </NavLink>
          </Button>
        ))}
        {(session?.user.manage_agent_prompts || session?.user.view_agent_observability) && (
          <p className="nav-section-label nav-secondary">ADMIN</p>
        )}
        {session?.user.manage_agent_prompts && (
          <Button asChild variant="ghost" className="workspace-link">
            <NavLink to="/admin/agent-prompts" onClick={onNavigate} title="Prompt catalog" aria-label="Prompt catalog">
              <SlidersHorizontal aria-hidden="true" />
              <span className="nav-copy">Prompt catalog</span>
            </NavLink>
          </Button>
        )}
        {session?.user.view_agent_observability && (
          <Button asChild variant="ghost" className="workspace-link">
            <NavLink to="/admin/agent-runs" onClick={onNavigate} title="Agent observability" aria-label="Agent observability">
              <Activity aria-hidden="true" />
              <span className="nav-copy">Agent observability</span>
            </NavLink>
          </Button>
        )}
      </nav>
      <div className="sidebar-bottom">
        <Button asChild variant="ghost" className="workspace-link">
          <Link
            to="/"
            onClick={onNavigate}
            aria-label="About PayScope"
            title="About PayScope"
          >
            <ArrowUpRight aria-hidden="true" />
            <span className="nav-copy">About PayScope</span>
          </Link>
        </Button>
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
  useEffect(() => {
    const media = matchMedia('(max-width: 1100px)')
    function resize(event) {
      setMobile(event.matches)
      if (!event.matches) setDrawerOpen(false)
    }
    media.addEventListener('change', resize)
    return () => media.removeEventListener('change', resize)
  }, [])
  const title =
    pages.find(
      (page) => page.path === pathname || pathname.startsWith(page.path + '/'),
    )?.label ||
    (pathname === '/activity' ? 'Activity' : pathname === '/admin/agent-prompts' ? 'Prompt catalog' : pathname.startsWith('/admin/agent-runs') ? 'Agent observability' : 'Workspace')
  const mobileNavigationToggle = (
    <Button
      variant="secondary"
      size="icon-lg"
      className="workspace-toggle"
      aria-label="Toggle navigation"
      title="Toggle navigation"
    >
      <PanelLeft aria-hidden="true" />
    </Button>
  )

  return (
    <div className={collapsed ? 'workspace-shell sidebar-collapsed' : 'workspace-shell'}>
      <aside id="workspace-sidebar" className="workspace-sidebar">
        <Navigation />
      </aside>
      <div className="workspace-body">
        <header className="workspace-topbar">
          <div className="topbar-location">
            {mobile ? (
              <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
                <SheetTrigger asChild>{mobileNavigationToggle}</SheetTrigger>
                <SheetContent side="left" className="workspace-drawer" aria-describedby={undefined}>
                  <SheetTitle className="sr-only">Workspace navigation</SheetTitle>
                  <Navigation onNavigate={() => setDrawerOpen(false)} />
                </SheetContent>
              </Sheet>
            ) : (
              <Button
                variant="secondary"
                size="icon-lg"
                className="workspace-toggle"
                aria-label="Toggle navigation"
                title="Toggle navigation"
                aria-expanded={!collapsed}
                aria-controls="workspace-sidebar"
                onClick={() => setCollapsed((previous) => !previous)}
              >
                <PanelLeft aria-hidden="true" />
              </Button>
            )}
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
