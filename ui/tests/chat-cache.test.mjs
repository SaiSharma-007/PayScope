import assert from 'node:assert/strict'
import { test } from 'node:test'
import { loadChat, saveChat } from '../src/features/agents/chatCache.js'

test('concurrent chat reads share a request and fresh snapshots avoid fetching', async (context) => {
  const cache = new Map()
  let finish
  const fetch = context.mock.method(globalThis, 'fetch', () => new Promise((resolve) => { finish = resolve }))
  const first = loadChat(cache, '/agent/conversations/one')
  const second = loadChat(cache, '/agent/conversations/one')
  assert.equal(first, second)
  finish({ ok: true, status: 200, json: async () => ({ id: 'one', turns: [] }) })
  await first
  assert.equal((await loadChat(cache, '/agent/conversations/one')).id, 'one')
  assert.equal(fetch.mock.callCount(), 1)
})

test('an evicted or replaced conversation cannot be resurrected by a late request', async (context) => {
  const cache = new Map()
  let finish
  context.mock.method(globalThis, 'fetch', () => new Promise((resolve) => { finish = resolve }))
  const pending = loadChat(cache, '/agent/conversations/one')
  cache.delete('/agent/conversations/one')
  finish({ ok: true, status: 200, json: async () => ({ id: 'one', turns: ['old'] }) })
  await pending
  assert.equal(cache.has('/agent/conversations/one'), false)
})

test('stale snapshots are refreshed and the in-memory cache stays bounded', async (context) => {
  const cache = new Map()
  saveChat(cache, '/agent/conversations/one', { id: 'old' })
  cache.get('/agent/conversations/one').savedAt -= 31_000
  context.mock.method(globalThis, 'fetch', async () => ({ ok: true, status: 200, json: async () => ({ id: 'fresh' }) }))
  assert.equal((await loadChat(cache, '/agent/conversations/one')).id, 'fresh')
  for (let index = 0; index < 100; index++) saveChat(cache, String(index), { id: index })
  assert.ok(cache.size <= 30)
  assert.equal(cache.has('/agent/conversations/one'), false)
})
