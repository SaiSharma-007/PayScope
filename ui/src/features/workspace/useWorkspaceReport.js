import { useEffect, useState } from 'react'
import { useCompensationApi } from '../compensation/shared'

export function useWorkspaceReport(path) {
  const api = useCompensationApi()
  const [attempt, setAttempt] = useState(0)
  const [response, setResponse] = useState(null)
  const key = `${path}:${attempt}`

  useEffect(() => {
    const controller = new AbortController()
    api(path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResponse({ key, data })
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setResponse((previous) => ({ key, data: previous?.data, error }))
      })
    return () => controller.abort()
  }, [api, key, path])

  return {
    data: response?.data,
    error: response?.key === key ? response.error : null,
    loading: response?.key !== key,
    retry: () => setAttempt((value) => value + 1),
  }
}
