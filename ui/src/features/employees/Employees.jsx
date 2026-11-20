import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Search, Users, X } from 'lucide-react'
import { request } from '../../lib/http'
import { useAuth } from '../auth/useAuth'
import SelectField from '../../components/SelectField'
import EmployeeTable from './EmployeeTable'

export default function Employees() {
  const { expire } = useAuth()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState(null)
  const [options, setOptions] = useState(null)
  const [referenceError, setReferenceError] = useState('')
  const [retry, setRetry] = useState(0)
  const tableRegion = useRef(null)
  const search = params.get('search') || ''
  const requestedPage = Number(params.get('page'))
  const page =
    Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  const pageSize = [10, 25, 50].includes(Number(params.get('page_size')))
    ? Number(params.get('page_size'))
    : 25
  const query = new URLSearchParams(params)
  query.set('page', page)
  query.set('page_size', pageSize)
  const key = query.toString()
  const requestKey = `${key}:${retry}`

  useEffect(() => {
    const controller = new AbortController()
    request('/reference-data', { signal: controller.signal })
      .then((options) => {
        if (controller.signal.aborted) return
        setOptions(options)
        setReferenceError('')
      })
      .catch((error) => {
        if (error.name === 'AbortError') return
        if (error.status === 401) expire()
        else setReferenceError('Filter options could not be loaded.')
      })
    return () => controller.abort()
  }, [expire, retry])

  useEffect(() => {
    const controller = new AbortController()
    request(`/employees?${key}`, { signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) {
          setData({ key: requestKey, result })
          if (tableRegion.current) tableRegion.current.scrollTop = 0
        }
      })
      .catch((error) => {
        if (error.name === 'AbortError') return
        if (error.status === 401) expire()
        else
          setData((previous) => ({
            ...previous,
            errorKey: requestKey,
            error: error.message,
          }))
      })
    return () => controller.abort()
  }, [key, requestKey, expire])

  function filter(name, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value)
    else next.delete(name)
    next.delete('page')
    setParams(next)
  }

  function retryDirectory() {
    setRetry((previous) => previous + 1)
  }

  const loading = data?.key !== requestKey && data?.errorKey !== requestKey
  const result = data?.result
  const error = data?.errorKey === requestKey ? data.error : null
  const hasFilters = [
    'search',
    'country_code',
    'department_id',
    'job_title_id',
  ].some((name) => params.get(name))
  function changePage(value) {
    const next = new URLSearchParams(params)
    next.set('page', value)
    setParams(next)
  }
  return (
    <main id="main" className="page employees-page">
      <div className="workspace-heading">
        <div>
          <span className="eyebrow">YOUR WORKSPACE</span>
          <h1>People, in focus.</h1>
          <p>Current salaries. A clearer place to start.</p>
        </div>
      </div>
      <section
        className="panel directory-panel"
        aria-labelledby="directory-title"
      >
        <div className="directory-heading">
          <div className="title-with-icon">
            <span className="icon-tile">
              <Users size={21} aria-hidden="true" />
            </span>
            <div>
              <h2 id="directory-title">Employees</h2>
              <p>
                {result
                  ? `${result.total.toLocaleString()} matching ${result.total === 1 ? 'employee' : 'employees'}`
                  : 'Finding your people…'}
              </p>
            </div>
          </div>
          <span className="demo-label">Fictional demo data</span>
        </div>
        <div className="directory-filters">
          <div className="search-group">
            <label htmlFor="employee-search">Search employees</label>
            <form
              className="search-field"
              role="search"
              noValidate
              onSubmit={(event) => {
                event.preventDefault()
                filter(
                  'search',
                  new FormData(event.currentTarget).get('search').trim(),
                )
              }}
            >
              <Search size={18} aria-hidden="true" />
              <input
                key={search}
                id="employee-search"
                name="search"
                defaultValue={search}
                placeholder="Name or employee ID"
                maxLength={100}
              />
              <button className="search-submit" type="submit">
                Search
              </button>
            </form>
          </div>
          {[
            ['country_code', 'Country', options?.countries, 'code'],
            ['department_id', 'Department', options?.departments, 'id'],
            ['job_title_id', 'Job title', options?.job_titles, 'id'],
          ].map(([name, label, entries, valueKey]) => (
            <SelectField
              key={name}
              id={name}
              label={label}
              disabled={!options}
              value={params.get(name) || ''}
              onChange={(value) => filter(name, value)}
              placeholder={`All ${label === 'Country' ? 'countries' : label.toLowerCase() + 's'}`}
              options={(entries || []).map((option) => ({
                value: String(option[valueKey]),
                label: option.name,
              }))}
            />
          ))}
        </div>
        {referenceError && (
          <div className="reference-error">
            <p className="error-message" role="alert">
              {referenceError}
            </p>
            <button className="text-link" onClick={() => setRetry(retry + 1)}>
              Retry filter options
            </button>
          </div>
        )}
        <div className="directory-status">
          <p role="status" aria-live="polite">
            {loading
              ? result
                ? 'Updating results… Previous results shown.'
                : 'Loading employees…'
              : error
                ? 'Results could not be updated.'
                : 'Annual gross base pay · original currency'}
          </p>
          {hasFilters && (
            <button className="clear-filters" onClick={() => setParams({})}>
              <X size={15} aria-hidden="true" />
              Clear filters
            </button>
          )}
        </div>
        {error && (
          <div className="directory-error">
            <p role="alert">{error}</p>
            <button className="button secondary" onClick={retryDirectory}>
              Try again
            </button>
          </div>
        )}
        <div
          className="table-region"
          ref={tableRegion}
          aria-label="Employee results"
          tabIndex={0}
          aria-busy={loading}
        >
          {!result && error ? (
            <div className="table-feedback">Employee results unavailable.</div>
          ) : !result ? (
            <div className="table-skeleton" aria-hidden="true">
              {Array.from({ length: 8 }, (_, index) => (
                <div className="skeleton-row" key={index}>
                  <span />
                  <span />
                  <span />
                  <span />
                </div>
              ))}
            </div>
          ) : result.items.length === 0 ? (
            <div className="table-feedback">
              <Search size={28} aria-hidden="true" />
              <h3>
                {result.total
                  ? 'No employees on this page.'
                  : 'No employees found.'}
              </h3>
              <p>
                {result.total
                  ? 'Return to the first page to see matching employees.'
                  : 'Try a different name or clear the filters.'}
              </p>
              <button
                className="button secondary"
                disabled={loading}
                onClick={() => (result.total ? changePage(1) : setParams({}))}
              >
                {result.total ? 'Go to first page' : 'Reset search'}
              </button>
            </div>
          ) : (
            <EmployeeTable employees={result.items} />
          )}
        </div>
        {result && (
          <div className="pagination">
            <span>
              {result.items.length
                ? `${((result.page - 1) * result.page_size + 1).toLocaleString()}–${Math.min(result.page * result.page_size, result.total).toLocaleString()} of ${result.total.toLocaleString()}`
                : result.total
                  ? `0 shown of ${result.total.toLocaleString()}`
                  : '0 employees'}
            </span>
            <div>
              <SelectField
                id="page_size"
                label="Rows per page"
                value={String(pageSize)}
                onChange={(value) => filter('page_size', value)}
                options={[10, 25, 50].map((size) => ({
                  value: String(size),
                  label: String(size),
                }))}
                disabled={loading}
              />
              <button
                className="button secondary compact"
                disabled={loading || result.page <= 1}
                onClick={() => changePage(result.page - 1)}
              >
                <ArrowLeft size={16} aria-hidden="true" />
                Previous
              </button>
              <button
                className="button secondary compact"
                disabled={
                  loading || result.page * result.page_size >= result.total
                }
                onClick={() => changePage(result.page + 1)}
              >
                Next
                <ArrowRight size={16} aria-hidden="true" />
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
