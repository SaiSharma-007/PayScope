import { Link } from 'react-router-dom'
import { ChartNoAxesCombined, Search, SlidersHorizontal } from 'lucide-react'
import { useAuth } from '../auth/useAuth'
import ProductPreview from './ProductPreview'

export default function Landing() {
  const auth = useAuth()
  return (
    <main id="main">
      <section className="hero page">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="eyebrow-rule" /> PEOPLE. PAY. PERSPECTIVE.
          </div>
          <h1>
            Employee pay,
            <br />
            <span>in perspective.</span>
          </h1>
          <p className="hero-description">
            A little less spreadsheet.
            <br />A lot more understanding.
          </p>
          <p className="hero-detail">
            Manage employee salaries and see how pay compares across your
            organisation, all in one workspace.
          </p>
          <div className="hero-actions">
            <Link
              className="button primary large"
              to={auth.session ? '/employees' : '/sign-in'}
            >
              {auth.session
                ? 'Open your workspace'
                : 'Explore the HR workspace'}
            </Link>
            <a className="text-link" href="#overview">
              Take a closer look
            </a>
          </div>
          <div className="hero-proof">
            <span className="proof-mark">
              <Search size={17} aria-hidden="true" />
            </span>
            <span>
              Built for 10,000 people.
              <br />
              <strong>Designed for the person looking after them.</strong>
            </span>
          </div>
        </div>
        <ProductPreview />
      </section>
      <section
        className="overview page"
        id="overview"
        aria-labelledby="overview-title"
      >
        <div className="overview-heading">
          <span className="eyebrow">THE EVERYDAY, SIMPLIFIED</span>
          <h2 id="overview-title">Employee salaries, together.</h2>
          <p>From finding one employee to understanding the bigger picture.</p>
        </div>
        <div className="feature-grid">
          <article>
            <span className="icon-tile">
              <Search size={22} aria-hidden="true" />
            </span>
            <h3>Employee directory</h3>
            <p>
              Search by name or employee ID. Narrow things down by country,
              department, and role.
            </p>
          </article>
          <article>
            <span className="icon-tile amber">
              <SlidersHorizontal size={22} aria-hidden="true" />
            </span>
            <h3>Current salary records</h3>
            <p>
              Current annual salaries, clearly recorded with their currency. One
              dependable place to start.
            </p>
          </article>
          <article>
            <span className="icon-tile">
              <ChartNoAxesCombined size={22} aria-hidden="true" />
            </span>
            <h3>Pay comparisons</h3>
            <p>
              Compare groups with minimum, median, average, and maximum pay,
              within each currency.
            </p>
          </article>
        </div>
        <Link
          className="button secondary overview-action"
          to={auth.session ? '/employees' : '/sign-in'}
        >
          Open the HR workspace
        </Link>
      </section>
      <footer className="page site-footer">
        <span>
          PayScope<span className="brand-period">.</span>
        </span>
        <p>An assessment demo. All employee data is fictional.</p>
        <span>Made for a clearer picture.</span>
      </footer>
    </main>
  )
}
