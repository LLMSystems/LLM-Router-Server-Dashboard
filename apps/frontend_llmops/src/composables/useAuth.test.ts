import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, getAdminToken } from '@/lib/api'
import { useAuth } from '@/composables/useAuth'

describe('useAuth gate', () => {
  beforeEach(() => useAuth().logout())
  afterEach(() => vi.restoreAllMocks())

  it('ensureUnlocked resolves true when auth is disabled', async () => {
    vi.spyOn(api, 'authStatus').mockResolvedValue({ auth_enabled: false })
    const { ensureUnlocked, refreshStatus, authEnabled } = useAuth()
    await refreshStatus()
    expect(authEnabled.value).toBe(false)
    expect(await ensureUnlocked()).toBe(true)
  })

  it('submitToken stores a verified token and marks unlocked', async () => {
    vi.spyOn(api, 'authVerify').mockResolvedValue(true)
    const { submitToken, hasToken } = useAuth()
    expect(await submitToken('good-token')).toBe(true)
    expect(getAdminToken()).toBe('good-token')
    expect(hasToken.value).toBe(true)
  })

  it('submitToken rejects an invalid token', async () => {
    vi.spyOn(api, 'authVerify').mockResolvedValue(false)
    const { submitToken, hasToken } = useAuth()
    expect(await submitToken('bad')).toBe(false)
    expect(hasToken.value).toBe(false)
  })
})
