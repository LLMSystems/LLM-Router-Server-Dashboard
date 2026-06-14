import { computed, ref } from 'vue'
import { api, clearAdminToken, getAdminToken, setAdminToken } from '@/lib/api'

// Module-level so the admin session is shared app-wide: the token is entered
// once, verified against the backend, then attached to every write by api.ts.
const token = ref(getAdminToken())
const authEnabled = ref<boolean | null>(null) // null = not yet queried
const dialogOpen = ref(false)
let resolver: ((ok: boolean) => void) | null = null

/**
 * Admin-token gate. Replaces the old client-side password: the backend decides
 * whether auth is required (`/api/auth/status`) and validates the token
 * (`/api/auth/verify`). When auth is disabled the gate is transparent.
 */
export function useAuth() {
  async function refreshStatus() {
    try {
      authEnabled.value = (await api.authStatus()).auth_enabled
    } catch {
      authEnabled.value = false // backend unreachable — don't block the UI
    }
  }

  const needsUnlock = computed(() => authEnabled.value === true && !token.value)

  /** Resolve true once the operator is unlocked, opening the dialog if needed. */
  async function ensureUnlocked(): Promise<boolean> {
    if (authEnabled.value === null) await refreshStatus()
    if (!authEnabled.value || token.value) return true
    dialogOpen.value = true
    return new Promise<boolean>((res) => {
      resolver = res
    })
  }

  /** Verify a candidate token; on success store it and release any waiter. */
  async function submitToken(input: string): Promise<boolean> {
    const ok = await api.authVerify(input)
    if (!ok) return false
    token.value = input
    setAdminToken(input)
    dialogOpen.value = false
    resolver?.(true)
    resolver = null
    return true
  }

  function cancel() {
    dialogOpen.value = false
    resolver?.(false)
    resolver = null
  }

  function logout() {
    token.value = ''
    clearAdminToken()
  }

  return {
    authEnabled,
    dialogOpen,
    needsUnlock,
    hasToken: computed(() => !!token.value),
    refreshStatus,
    ensureUnlocked,
    submitToken,
    cancel,
    logout,
  }
}
