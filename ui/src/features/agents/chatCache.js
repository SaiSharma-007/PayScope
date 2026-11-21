import { request } from '../../lib/http.js'

const TTL = 30_000
const MAX_ENTRIES = 30

export function saveChat(cache, key, data) {
  cache.delete(key)
  cache.set(key, { data, savedAt: Date.now() })
  while (cache.size > MAX_ENTRIES) cache.delete(cache.keys().next().value)
}

export function loadChat(cache, key) {
  const existing = cache.get(key)
  if (existing?.pending) return existing.pending
  if (existing?.data && Date.now() - existing.savedAt < TTL)
    return Promise.resolve(existing.data)
  const entry = { ...existing }
  entry.pending = request(key).then(
    (data) => {
      if (cache.get(key) === entry) saveChat(cache, key, data)
      return data
    },
    (error) => {
      if (cache.get(key) === entry) cache.delete(key)
      throw error
    },
  )
  cache.set(key, entry)
  return entry.pending
}
