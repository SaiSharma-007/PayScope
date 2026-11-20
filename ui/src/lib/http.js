export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export async function request(path, { csrf, ...options } = {}) {
  let response
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      signal: AbortSignal.any([
        AbortSignal.timeout(15000),
        ...(options.signal ? [options.signal] : []),
      ]),
      credentials: 'same-origin',
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
        ...options.headers,
      },
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Couldn’t connect. Check your connection and try again.',
      0,
    )
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    const message =
      typeof detail === 'object' && !Array.isArray(detail)
        ? detail?.message
        : null
    throw new ApiError(
      message || 'This request could not be completed. Please try again.',
      response.status,
    )
  }
  return response.status === 204 ? null : response.json()
}
