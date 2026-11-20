import { useEffect, useMemo, useState } from 'react'
import { useCompensationApi } from '../compensation/shared'

export function useWorkspaceReport(path) {
  const api = useCompensationApi()
  const [attempt, setAttempt] = useState(0)
  const [response, setResponse] = useState(null)
  const request = useMemo(() => ({ path, attempt }), [path, attempt])

  useEffect(() => {
    const controller = new AbortController()
    api(request.path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResponse({ request, data })
      })
      .catch((error) => {
        if (!controller.signal.aborted) setResponse({ request, error })
      })
    return () => controller.abort()
  }, [api, request])

  return {
    data: response?.request === request ? response.data : null,
    error: response?.request === request ? response.error : null,
    loading: response?.request !== request,
    retry: () => setAttempt((value) => value + 1),
  }
}
