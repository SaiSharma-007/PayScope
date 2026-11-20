import { useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, Plus, SlidersHorizontal } from 'lucide-react'
import SelectField from '../../components/SelectField'
import Skeleton from '../../components/Skeleton'
import { ErrorSummary } from './Fields'
import { useReferenceData } from './shared'
import { useWorkspaceReport } from '../workspace/useWorkspaceReport'

export default function Rules() {
  const reference = useReferenceData()
  const [params, setParams] = useSearchParams()
  const results = useRef(null)
  const query = new URLSearchParams()
  for (const name of ['country_code', 'currency_code', 'active', 'page'])
    if (params.get(name)) query.set(name, params.get(name))
  const { data, loading, error, retry } = useWorkspaceReport(
    `/compensation/rules?${query}`,
  )
  function filter(name, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value)
    else next.delete(name)
    next.delete('page')
    setParams(next)
  }
  function changePage(page) {
    results.current?.focus({ preventScroll: true })
    results.current?.scrollIntoView({ block: 'start' })
    setParams({ ...Object.fromEntries(params), page })
  }
  return (
    <main id="main" className="page rules-page">
      <div className="workspace-heading">
        <div>
          <span className="eyebrow">COMPENSATION RULES</span>
          <h1>A structure for every package.</h1>
          <p>Define the components. See how every amount is calculated.</p>
        </div>
        <Link className="button primary" to="/rules/new">
          <Plus size={18} aria-hidden="true" />
          Create rule
        </Link>
      </div>
      <section className="panel rules-panel" aria-labelledby="rules-title">
        <div className="comp-section-heading">
          <div className="title-with-icon">
            <span className="icon-tile">
              <SlidersHorizontal size={21} aria-hidden="true" />
            </span>
            <div>
              <h2 id="rules-title">Company rules</h2>
              <p>Country-specific, reusable, and versioned.</p>
            </div>
          </div>
        </div>
        <div className="rules-filters">
          <SelectField
            id="rules-country"
            label="Country"
            value={params.get('country_code') || ''}
            placeholder="All countries"
            disabled={!reference.data}
            options={(reference.data?.countries || []).map((item) => ({
              value: item.code,
              label: item.name,
            }))}
            onChange={(value) => filter('country_code', value)}
          />
          <SelectField
            id="rules-currency"
            label="Currency"
            value={params.get('currency_code') || ''}
            placeholder="All currencies"
            disabled={!reference.data}
            options={(reference.data?.currencies || []).map((item) => ({
              value: item.code,
              label: item.code,
            }))}
            onChange={(value) => filter('currency_code', value)}
          />
          <SelectField
            id="rules-status"
            label="Status"
            value={params.get('active') || ''}
            placeholder="All rules"
            options={[
              { value: 'true', label: 'Active' },
              { value: 'false', label: 'Inactive' },
            ]}
            onChange={(value) => filter('active', value)}
          />
        </div>
        {reference.error && (
          <div>
            <ErrorSummary error={reference.error} />
            <button className="text-link" onClick={reference.retry}>
              Retry filter options
            </button>
          </div>
        )}
        <ErrorSummary error={error} />
        {error && (
          <button className="button secondary" onClick={retry}>
            Try again
          </button>
        )}
        <p className="comp-status" role="status">
          {loading
            ? 'Loading rules…'
            : !error && data
              ? `${data.total} ${data.total === 1 ? 'rule' : 'rules'}`
              : ''}
        </p>
        <div
          className="rule-list"
          role="region"
          aria-label="Rule results"
          ref={results}
          tabIndex={-1}
          aria-busy={loading}
        >
          {loading ? (
            Array.from({ length: data?.items.length || 4 }, (_, index) => (
              <div className="rule-list-row" key={index} aria-hidden="true">
                <Skeleton width="42px" height="42px" />
                <span className="rule-list-name">
                  <Skeleton width="min(70%, 13rem)" />
                  <Skeleton width="5rem" height="0.6rem" />
                </span>
                <Skeleton width="3rem" height="1rem" />
              </div>
            ))
          ) : error ? (
            <div className="comp-empty">Rule results unavailable.</div>
          ) : data?.items.length === 0 ? (
            <div className="comp-empty">
              <h3>No rules match.</h3>
              <p>Create a rule or choose different filters.</p>
            </div>
          ) : (
            data?.items.map((rule) => (
              <Link
                className="rule-list-row"
                key={rule.id}
                to={`/rules/${rule.id}`}
              >
                <span className="rule-country">{rule.country_code}</span>
                <span className="rule-list-name">
                  <strong>{rule.name}</strong>
                  <small>
                    {rule.currency_code} · Version {rule.latest_version}
                  </small>
                </span>
                <span
                  className={`rule-state${rule.active ? ' is-active' : ''}`}
                >
                  {rule.active ? 'Active' : 'Inactive'}
                </span>
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            ))
          )}
        </div>
        {data && !error && data.total > 50 && (
          <div className="pagination">
            <span>
              {loading ? <Skeleton width="3rem" /> : `Page ${data.page}`}
            </span>
            <div>
              <button
                className="button secondary compact"
                disabled={loading || data.page <= 1}
                onClick={() => changePage(data.page - 1)}
              >
                Previous
              </button>
              <button
                className="button secondary compact"
                disabled={loading || data.page * 50 >= data.total}
                onClick={() => changePage(data.page + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}
        <p className="comp-footnote">
          Rules describe your company’s package structure. They do not
          automatically apply statutory contribution or tax rates.
        </p>
      </section>
    </main>
  )
}
