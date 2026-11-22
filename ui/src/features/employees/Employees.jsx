import { Input } from '../../components/ui/input'
import { Button } from '../../components/ui/button'
import { FieldGroup } from '../../components/ui/field'
import { InputGroup, InputGroupAddon, InputGroupInput } from '../../components/ui/input-group'
import { Sheet, SheetClose, SheetContent, SheetTitle, SheetTrigger } from '../../components/ui/sheet'
import { toast } from 'sonner'
import { SelectPortalContext } from '../../components/SelectPortalContext'
import './employees.css'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Search, SlidersHorizontal, X } from 'lucide-react'
import { request } from '../../lib/http'
import { useAuth } from '../auth/useAuth'
import SelectField from '../../components/SelectField'
import Skeleton from '../../components/Skeleton'
import EmployeeTable from './EmployeeTable'
const CompensationDrawer = lazy(
  () => import('../compensation/CompensationDrawer'),
)

export default function Employees() {
  const { expire } = useAuth()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState(null)
  const [options, setOptions] = useState(null)
  const [referenceError, setReferenceError] = useState('')
  const [retry, setRetry] = useState(0)
  const [selectedEmployee, setSelectedEmployee] = useState(null)
  const [filterPortal, setFilterPortal] = useState(null)
  const tableRegion = useRef(null)
  const search = params.get('search') || ''
  const requestedPage = Number(params.get('page'))
  const page =
    Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  const pageSize = [10, 25, 50].includes(Number(params.get('page_size')))
    ? Number(params.get('page_size'))
    : 10
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
  const result = data?.key === requestKey ? data.result : null
  const previousResult = data?.result
  const paginationResult = loading ? previousResult : result
  const pageCount = paginationResult ? Math.ceil(paginationResult.total / paginationResult.page_size) : 0
  const error = data?.errorKey === requestKey ? data.error : null
  const hasFilters = [
    'search',
    'country_code',
    'department_id',
    'job_title_id',
    'pay_status',
  ].some((name) => params.get(name))
  function changePage(value) {
    if (tableRegion.current) tableRegion.current.scrollTop = 0
    tableRegion.current?.focus({ preventScroll: true })
    const next = new URLSearchParams(params)
    next.set('page', value)
    setParams(next)
  }
  const filterOptions = [
    ['country_code', 'Country', options?.countries, 'code', 'All countries'],
    ['department_id', 'Department', options?.departments, 'id', 'All departments'],
    ['job_title_id', 'Job title', options?.job_titles, 'id', 'All job titles'],
    ['pay_status', 'Base pay', [
      { id: 'recorded', name: 'Base pay on file' },
      { id: 'missing', name: 'Missing base pay' },
    ], 'id', 'Any pay status'],
  ]

  const activeFilters = filterOptions
    .filter(([name]) => params.has(name))
    .map(([name, label, entries, valueKey]) => ({
      name,
      label,
      value: entries?.find((entry) => String(entry[valueKey]) === params.get(name))?.name || params.get(name),
    }))

  function renderFilters(surface) {
    return filterOptions.map(([name, label, entries, valueKey, placeholder]) => (
      <SelectField key={name} id={`${surface}-${name}`} label={label}
        disabled={!entries} value={params.get(name) || ''}
        onChange={(value) => filter(name, value)} placeholder={placeholder}
        options={(entries || []).map((entry) => ({ value: String(entry[valueKey]), label: entry.name }))}
      />
    ))
  }

  return (
    <main id="main" className="page employees-page">
      <section
        className="panel directory-panel"
        aria-labelledby="directory-title"
      >
        <div className="directory-heading">
          <div className="directory-title">
            <h1 id="directory-title">Employees</h1>
            <p>
              {loading ? (
                <Skeleton width="9rem" />
              ) : result ? (
                `${result.total.toLocaleString()} matching ${result.total === 1 ? 'employee' : 'employees'}`
              ) : (
                'Employee count unavailable'
              )}
            </p>
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
              <InputGroup>
                <InputGroupAddon><Search aria-hidden="true" /></InputGroupAddon>
                <InputGroupInput
                key={search}
                id="employee-search"
                name="search"
                defaultValue={search}
                placeholder="Name or ID"
                maxLength={100}
              />
              </InputGroup>
              <Button className="search-submit" type="submit">Search</Button>
            </form>
          </div>
          <FieldGroup className="directory-desktop-filters">
            {renderFilters('desktop')}
          </FieldGroup>
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="secondary" className="directory-filter-trigger">
                <SlidersHorizontal data-icon="inline-start" />
                Filters{activeFilters.length ? ` (${activeFilters.length})` : ''}
              </Button>
            </SheetTrigger>
            <SheetContent ref={setFilterPortal} className="directory-filter-sheet" aria-describedby={undefined}>
              <SheetTitle>Filter employees</SheetTitle>
              <SelectPortalContext value={filterPortal}>
                <FieldGroup>{renderFilters('mobile')}</FieldGroup>
              </SelectPortalContext>
              <SheetClose asChild>
                <Button>Show employees</Button>
              </SheetClose>
            </SheetContent>
          </Sheet>
        </div>
        {activeFilters.length > 0 && (
          <div className="directory-applied" aria-label="Applied filters">
            {activeFilters.map(({ name, label, value }) => (
              <Button key={name} variant="secondary" size="sm" onClick={() => filter(name, '')}
                aria-label={`Remove ${label} filter: ${value}`}>
                {value}<X data-icon="inline-end" />
              </Button>
            ))}
          </div>
        )}
        {referenceError && (
          <div className="reference-error">
            <p className="error-message" role="alert">
              {referenceError}
            </p>
            <Button className="text-link" onClick={() => setRetry(retry + 1)}>
              Retry filter options
            </Button>
          </div>
        )}
        <div className="directory-status">
          <p role="status" aria-live="polite">
            {loading
              ? previousResult
                ? 'Updating employee results…'
                : 'Loading employees…'
              : error
                ? 'Results could not be updated.'
                : 'Annual cash & benefits · original currency'}
          </p>
          {hasFilters && (
            <Button className="clear-filters" onClick={() => setParams({})}>
              <X size={15} aria-hidden="true" />
              Clear filters
            </Button>
          )}
        </div>
        {error && (
          <div className="directory-error">
            <p role="alert">{error}</p>
            <Button variant="secondary" onClick={retryDirectory}>
              Try again
            </Button>
          </div>
        )}
        {pageCount > 0 && (
          <nav
            className="pagination directory-pagination"
            aria-label="Employee pages"
          >
            <span>
              {loading ? (
                <Skeleton width="7rem" />
              ) : result.items.length ? (
                `${((result.page - 1) * result.page_size + 1).toLocaleString()}–${Math.min(result.page * result.page_size, result.total).toLocaleString()} of ${result.total.toLocaleString()}`
              ) : result.total ? (
                `0 shown of ${result.total.toLocaleString()}`
              ) : (
                '0 employees'
              )}
            </span>
            <div>
              <form
                className="directory-page-jump"
                onSubmit={(event) => {
                  event.preventDefault()
                  const target = Number(new FormData(event.currentTarget).get('page'))
                  if (result && Number.isSafeInteger(target) && target >= 1 && target <= Math.ceil(result.total / result.page_size)) changePage(target)
                }}
              >
                <label htmlFor="directory-page">Page</label>
                <Input
                  key={page}
                  id="directory-page"
                  name="page"
                  type="number"
                  min={1}
                  max={pageCount}
                  defaultValue={page}
                  required
                  disabled={loading}
                />
                <span>of {pageCount.toLocaleString()}</span>
                <Button type="submit" variant="outline" disabled={loading}>Go</Button>
              </form>
              <SelectField
                id="page_size"
                label="Rows per page"
                value={String(paginationResult.page_size)}
                onChange={(value) => filter('page_size', value)}
                options={[10, 25, 50].map((size) => ({
                  value: String(size),
                  label: String(size),
                }))}
                disabled={loading}
              />
              <Button
                variant="secondary"
                disabled={loading || result.page <= 1}
                onClick={() => changePage(result.page - 1)}
              >
                <ArrowLeft size={16} aria-hidden="true" />
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={
                  loading || result.page * result.page_size >= result.total
                }
                onClick={() => changePage(result.page + 1)}
              >
                Next
                <ArrowRight size={16} aria-hidden="true" />
              </Button>
            </div>
          </nav>
        )}
        <div
          className="table-region"
          ref={tableRegion}
          role="region"
          aria-label="Employee results"
          tabIndex={0}
          aria-busy={loading}
        >
          {error ? (
            <div className="table-feedback">Employee results unavailable.</div>
          ) : loading ? (
            <EmployeeTable
              skeletonRows={
                previousResult?.items.length || Math.min(pageSize, 10)
              }
            />
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
              <Button
                variant="secondary"
                disabled={loading}
                onClick={() => (result.total ? changePage(1) : setParams({}))}
              >
                {result.total ? 'Go to first page' : 'Reset search'}
              </Button>
            </div>
          ) : (
            <EmployeeTable
              employees={result.items}
              onCompensation={setSelectedEmployee}
            />
          )}
        </div>
      </section>
      {selectedEmployee && (
        <Suspense
          fallback={
            <p className="comp-status" role="status">
              Opening compensation…
            </p>
          }
        >
          <CompensationDrawer
            key={selectedEmployee.id}
            employee={selectedEmployee}
            onClose={() => setSelectedEmployee(null)}
            onSaved={(packageData) => {
              toast.success('Compensation saved')
              if (params.get('pay_status')) {
                retryDirectory()
                return
              }
              setData((previous) => ({
                ...previous,
                result: {
                  ...previous.result,
                  items: previous.result.items.map((employee) =>
                    employee.id === selectedEmployee.id
                      ? { ...employee, compensation: packageData }
                      : employee,
                  ),
                },
              }))
            }}
          />
        </Suspense>
      )}
    </main>
  )
}
