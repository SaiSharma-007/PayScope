import {
  ArrowRight,
  ChartNoAxesCombined,
  Check,
  Clock3,
  Globe2,
  Users,
} from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

const content = {
  '/overview': {
    title: 'Your people. The bigger picture.',
    description: 'A first look at how your HR workspace comes together.',
  },
  '/insights': {
    title: 'Make room for better pay decisions.',
    description: 'Explore the shape of the upcoming salary insights workspace.',
  },
  '/activity': {
    title: 'Every change has a story.',
    description: 'A preview of how recent salary activity will appear here.',
  },
}
const departments = [
  { name: 'Engineering', count: '4,200', width: '84%' },
  { name: 'Operations', count: '2,100', width: '42%' },
  { name: 'Sales', count: '1,800', width: '36%' },
  { name: 'Other teams', count: '1,900', width: '38%' },
]

export default function WorkspacePreview() {
  const { pathname } = useLocation()
  const page = content[pathname]
  return (
    <main id="main" className="page workspace-preview-page">
      <div className="workspace-heading">
        <div>
          <span className="eyebrow">WORKSPACE PREVIEW</span>
          <h1>{page.title}</h1>
          <p>{page.description}</p>
        </div>
      </div>
      <p className="preview-notice">
        <Clock3 size={17} aria-hidden="true" />
        Sample content for this layout. Figures and activity below are
        illustrative.
      </p>
      {pathname !== '/activity' && (
        <>
          <div className="workspace-metrics">
            {[
              {
                label: 'People across the organization',
                value: '10,000',
                detail: 'Sample workforce',
                icon: Users,
              },
              {
                label: 'Countries represented',
                value: '5',
                detail: 'One connected workspace',
                icon: Globe2,
              },
              {
                label: 'Salary coverage',
                value: '98.4%',
                detail: 'Illustrative completeness',
                icon: ChartNoAxesCombined,
              },
            ].map(({ label, value, detail, icon: Icon }) => (
              <section className="panel workspace-metric" key={label}>
                <div>
                  <span>{label}</span>
                  <Icon size={20} aria-hidden="true" />
                </div>
                <strong>{value}</strong>
                <p>{detail}</p>
              </section>
            ))}
          </div>
          <div className="workspace-preview-grid">
            <section className="panel department-preview">
              <div className="preview-panel-heading">
                <div>
                  <h2>People by department</h2>
                  <p>Illustrative team distribution</p>
                </div>
                <span className="demo-label">Sample</span>
              </div>
              <div className="department-bars">
                {departments.map((department) => (
                  <div key={department.name}>
                    <div>
                      <span>{department.name}</span>
                      <strong>{department.count}</strong>
                    </div>
                    <div className="department-track">
                      <span style={{ width: department.width }} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
            <section className="panel workspace-next">
              <span className="icon-tile">
                <Users size={23} aria-hidden="true" />
              </span>
              <h2>Start with your people.</h2>
              <p>
                Search employees, narrow by team or country, and review current
                salaries in the directory.
              </p>
              <Link className="button primary" to="/employees">
                Open employee directory
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            </section>
          </div>
        </>
      )}
      {pathname === '/activity' && (
        <section className="panel activity-preview">
          <div className="preview-panel-heading">
            <div>
              <h2>Recent activity</h2>
              <p>Example entries for the upcoming activity feed</p>
            </div>
            <span className="demo-label">Sample</span>
          </div>
          {[
            {
              title: 'Salary details updated',
              detail: 'Aarav Mehta · Engineering',
              time: 'Today, 10:42 AM',
            },
            {
              title: 'New employee added',
              detail: 'Emma Fischer · Operations',
              time: 'Today, 9:18 AM',
            },
            {
              title: 'Salary review completed',
              detail: 'Sales · Quarterly review',
              time: 'Yesterday, 4:30 PM',
            },
          ].map((item) => (
            <div className="activity-preview-row" key={item.title}>
              <span className="icon-tile">
                <Check size={18} aria-hidden="true" />
              </span>
              <div>
                <strong>{item.title}</strong>
                <p>{item.detail}</p>
              </div>
              <span>{item.time}</span>
            </div>
          ))}
        </section>
      )}
    </main>
  )
}
