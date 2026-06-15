import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, clearAdminToken, getAdminToken, setAdminToken } from '@/lib/api'

function mockFetch() {
  const fn = vi.fn(async (_url: string, _init?: RequestInit) => ({
    ok: true,
    status: 200,
    statusText: 'OK',
    text: async () => '[]',
  }))
  vi.stubGlobal('fetch', fn)
  return fn
}

function headersOf(init?: RequestInit): Record<string, string> {
  return (init?.headers ?? {}) as Record<string, string>
}

describe('admin token', () => {
  beforeEach(() => clearAdminToken())
  afterEach(() => vi.unstubAllGlobals())

  it('persists and clears the token', () => {
    setAdminToken('tok')
    expect(getAdminToken()).toBe('tok')
    clearAdminToken()
    expect(getAdminToken()).toBe('')
  })

  it('attaches X-Admin-Token to backend requests when set', async () => {
    const f = mockFetch()
    setAdminToken('sekret')
    await api.listModels()
    const headers = headersOf(f.mock.calls[0]![1])
    expect(headers['X-Admin-Token']).toBe('sekret')
  })

  it('omits the auth header when no token is set', async () => {
    const f = mockFetch()
    await api.listModels()
    const headers = headersOf(f.mock.calls[0]![1])
    expect(headers['X-Admin-Token']).toBeUndefined()
  })

  it('sends a Bearer token on routerFetch when set', async () => {
    const f = mockFetch()
    setAdminToken('sekret')
    await api.routerFetch('/v1/models', { headers: { 'X-Test': '1' } })
    const headers = headersOf(f.mock.calls[0]![1])
    expect(headers.Authorization).toBe('Bearer sekret')
    expect(headers['X-Test']).toBe('1') // caller headers preserved
  })
})
