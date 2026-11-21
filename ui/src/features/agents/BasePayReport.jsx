import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { request } from '../../lib/http'
import { useAuth } from '../auth/useAuth'
import ReportChart from './ReportChart'
import './agents.css'

const columns = [
  ['minimum', 'Minimum'],
  ['median', 'Median'],
  ['mean', 'Average'],
  ['maximum', 'Maximum'],
]
const filters = [
  'country_code',
  'department_id',
  'job_title_id',
  'group_by',
  'currency_code',
]

export default function BasePayReport() {
  const [params] = useSearchParams()
  const query = new URLSearchParams(
    filters.flatMap((key) => (params.has(key) ? [[key, params.get(key)]] : [])),
  ).toString()
  const [result, setResult] = useState(null)
  const [attempt, setAttempt] = useState(0)
  const { expire } = useAuth()
  useEffect(() => {
    const controller = new AbortController()
    request(`/analytics/salary-summary?${query}`, { signal: controller.signal })
      .then((data) => setResult({ query, attempt, data }))
      .catch((error) => {
        if (error.name !== 'AbortError') {
          if (error.status === 401) expire()
          setResult({ query, attempt, error: error.message })
        }
      })
    return () => controller.abort()
  }, [query, attempt, expire])
  const current =
    result?.query === query && result?.attempt === attempt ? result : null
  const sourceRevision = params.get('revision')
  const changed =
    current?.data &&
    sourceRevision !== null &&
    current.data.revision > Number(sourceRevision)
  return (
    <main id="main" className="page agent-page">
      <header className="agent-heading">
        <div>
          <Link
            to={`/insights/ask${params.has('chat') ? `?chat=${encodeURIComponent(params.get('chat'))}` : ''}`}
          >
            Back to Ask about pay
          </Link>
          <h1 tabIndex={-1}>Annual base pay</h1>
        </div>
      </header>
      <section className="agent-panel">
        {changed && (
          <p role="status" className="agent-notice">
            Salary data has changed since this answer. The saved figures are
            still available in the chat.
          </p>
        )}
        {!current ? (
          <p role="status">Loading report…</p>
        ) : current.error ? (
          <p role="alert">
            {current.error}{' '}
            <button
              className="button secondary"
              onClick={() => setAttempt(attempt + 1)}
            >
              Retry
            </button>
          </p>
        ) : (
          <>
            <ReportChart report={current.data} snapshot={false} />
            <h2>Exact values</h2>
            {current.data.rows.length === 0 ? (
              <p>No recorded salaries match these filters.</p>
            ) : (
              <div className="agent-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Group</th>
                      <th scope="col">Currency</th>
                      <th scope="col">Employees</th>
                      {columns.map(([key, label]) => (
                        <th scope="col" key={key}>
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {current.data.rows.map((row) => (
                      <tr key={`${row.currency_code}-${row.group_id}`}>
                        <th scope="row">
                          {row.group_name || 'All matching employees'}
                        </th>
                        <td>{row.currency_code}</td>
                        <td>{row.headcount}</td>
                        {columns.map(([key]) => (
                          <td key={key}>{row[key]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>
    </main>
  )
}
