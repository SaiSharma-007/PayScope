import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, Plus, SlidersHorizontal } from 'lucide-react'
import SelectField from '../../components/SelectField'
import { ErrorSummary } from './Fields'
import { useCompensationApi, useReferenceData } from './shared'

export default function Rules() {
  const api = useCompensationApi()
  const reference = useReferenceData()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [retry, setRetry] = useState(0)
  const query = new URLSearchParams()
  for (const name of ['country_code', 'currency_code', 'active', 'page'])
    if (params.get(name)) query.set(name, params.get(name))
  const key = query.toString()
  useEffect(() => {
    const controller = new AbortController()
    api(`/compensation/rules?${key}`, { signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) {
          setData({ key, ...result })
          setError(null)
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(error)
      })
    return () => controller.abort()
  }, [api, key, retry])
  const loading = !error && data?.key !== key
  function filter(name, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value)
    else next.delete(name)
    next.delete('page')
    setParams(next)
    setError(null)
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
          <button
            className="button secondary"
            onClick={() => {
              setError(null)
              setRetry((value) => value + 1)
            }}
          >
            Try again
          </button>
        )}
        <p className="comp-status" role="status">
          {loading
            ? 'Loading rules…'
            : data
              ? `${data.total} ${data.total === 1 ? 'rule' : 'rules'}`
              : ''}
        </p>
        <div className="rule-list" aria-busy={loading}>
          {!data && loading ? (
            <div className="comp-empty">
              Loading your compensation structures…
            </div>
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
        {data && data.total > 50 && (
          <div className="pagination">
            <span>Page {data.page}</span>
            <div>
              <button
                className="button secondary compact"
                disabled={loading || data.page <= 1}
                onClick={() =>
                  setParams({
                    ...Object.fromEntries(params),
                    page: data.page - 1,
                  })
                }
              >
                Previous
              </button>
              <button
                className="button secondary compact"
                disabled={loading || data.page * 50 >= data.total}
                onClick={() =>
                  setParams({
                    ...Object.fromEntries(params),
                    page: data.page + 1,
                  })
                }
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
