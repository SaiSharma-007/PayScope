import { useCallback, useEffect, useState } from 'react'
import { request } from '../../lib/http'
import { useAuth } from '../auth/useAuth'

export function useCompensationApi() {
  const { session, expire } = useAuth()
  return useCallback(
    async (path, options = {}) => {
      try {
        return await request(path, { ...options, csrf: session.csrf_token })
      } catch (error) {
        if (error.status === 401) expire()
        throw error
      }
    },
    [session.csrf_token, expire],
  )
}

export function useReferenceData() {
  const api = useCompensationApi()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    api('/reference-data', { signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) {
          setData(result)
          setError(null)
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(error)
      })
    return () => controller.abort()
  }, [api, retry])
  return { data, error, retry: () => setRetry((value) => value + 1) }
}

export function money(amount, currency) {
  if (amount == null) return 'Not entered'
  const [whole, fraction = ''] = String(amount).split('.')
  return `${currency} ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`
}

export function today() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

export function errorsFor(error, path) {
  return error?.fields
    ?.filter((field) => field.loc.slice(1).join('.') === path)
    .map((field) => field.msg)
    .join(' ')
}

export const newComponent = () => ({
  code: '',
  label: '',
  category: 'earning',
  method: 'fixed',
  value: '',
  commitment: 'guaranteed',
  included_in_cost: true,
})

export function toDefinition(line) {
  return Object.fromEntries(
    [
      'code',
      'label',
      'category',
      'method',
      'value',
      'commitment',
      'included_in_cost',
    ].map((key) => [
      key,
      key === 'value'
        ? String(line[key]).replace(/(\.\d*?[1-9])0+$|\.0+$/, '$1')
        : line[key],
    ]),
  )
}
