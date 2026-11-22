import { Button } from '../../components/ui/button'
import { FieldGroup } from '../../components/ui/field'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table'
import { useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, Plus } from 'lucide-react'
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
    setParams({ ...Object.fromEntries(params), page })
  }
  return (
    <main id="main" className="page rules-page">
      <div className="workspace-heading">
        <div>
          <h1>Compensation rules</h1>
        </div>
        <Button asChild size="lg"><Link to="/rules/new"><Plus data-icon="inline-start" />New rule</Link></Button>
      </div>
      <section className="rules-panel" aria-label="Company rules">
        <FieldGroup className="rules-filters">
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
        </FieldGroup>
        {reference.error && (
          <div>
            <ErrorSummary error={reference.error} />
            <Button className="text-link" onClick={reference.retry}>
              Retry filter options
            </Button>
          </div>
        )}
        <ErrorSummary error={error} />
        {error && (
          <Button variant="secondary" onClick={retry}>
            Try again
          </Button>
        )}
        <p className="comp-status" role="status">
          {loading
            ? 'Loading rules…'
            : !error && data
              ? `${data.total} ${data.total === 1 ? 'rule' : 'rules'}`
              : ''}
        </p>
        {data && !error && data.total > 50 && (
          <div className="pagination rules-pagination">
            <span>
              {loading ? <Skeleton width="3rem" /> : `Page ${data.page} of ${Math.ceil(data.total / 50)}`}
            </span>
            <div>
              <Button
                variant="secondary"
                disabled={loading || data.page <= 1}
                onClick={() => changePage(data.page - 1)}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={loading || data.page * 50 >= data.total}
                onClick={() => changePage(data.page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
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
            <Table className="rules-table" role="table">
              <TableHeader role="rowgroup">
                <TableRow role="row">
                  <TableHead role="columnheader" scope="col">Rule</TableHead>
                  <TableHead role="columnheader" scope="col">Country</TableHead>
                  <TableHead role="columnheader" scope="col">Currency</TableHead>
                  <TableHead role="columnheader" scope="col">Latest version</TableHead>
                  <TableHead role="columnheader" scope="col">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody role="rowgroup">
                {data?.items.map((rule) => (
                  <TableRow role="row" key={rule.id}>
                    <TableCell role="cell">
                      <Button asChild variant="ghost" className="rule-name-link">
                        <Link to={`/rules/${rule.id}`}>
                          {rule.name}<ArrowRight data-icon="inline-end" />
                        </Link>
                      </Button>
                    </TableCell>
                    <TableCell role="cell" data-label="Country">{reference.data?.countries.find((country) => country.code === rule.country_code)?.name || rule.country_code}</TableCell>
                    <TableCell role="cell" data-label="Currency">{rule.currency_code}</TableCell>
                    <TableCell role="cell" data-label="Latest version">v{rule.latest_version}</TableCell>
                    <TableCell role="cell" data-label="Status">
                      <span className="rule-state" data-active={rule.active}>
                        {rule.active ? 'Active' : 'Inactive'}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
        <p className="comp-footnote">
          Rules describe your company’s package structure. They do not
          automatically apply statutory contribution or tax rates.
        </p>
      </section>
    </main>
  )
}
