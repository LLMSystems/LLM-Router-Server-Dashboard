import { computed } from 'vue'
import { useModelsStore } from '@/stores/models'
import { toast } from '@/lib/toast'
import { ApiError } from '@/lib/api'
import { useAuth } from '@/composables/useAuth'

type Action = 'start' | 'stop'

/**
 * Admin-gated start/stop, single or bulk. Routed through the shared admin-token
 * gate (useAuth): the first protected action prompts for the token when the
 * backend requires one, then stays unlocked for the session.
 */
export function useModelControl() {
  const models = useModelsStore()
  const { ensureUnlocked } = useAuth()

  // Only one LLM may be in the `starting` phase at a time — loading two model
  // weights at once OOMs a single GPU. Multiple *ready* LLMs are fine, and
  // embeddings (a separate service) are unrestricted.
  const isLlmStarting = computed(() => models.llms.some((m) => m.state === 'starting'))
  function startingLlmName(): string | null {
    const m = models.llms.find((x) => x.state === 'starting')
    return m ? (m.key.split('::')[0] ?? m.key) : null
  }
  /** True if starting `key` right now would put a second LLM into `starting`. */
  function isStartBlocked(key: string): boolean {
    const m = models.byKey.get(key)
    if (!m || m.kind !== 'llm') return false
    return models.llms.some((x) => x.key !== key && x.state === 'starting')
  }

  /** Resolve once `key` has left the `starting` phase (ready/failed/stopped). */
  function waitUntilNotStarting(key: string): Promise<void> {
    return new Promise((resolve) => {
      // Safety net: the backend caps `starting` via start_timeout, so this is
      // only here to guarantee the queue can never wedge.
      const deadline = Date.now() + 10 * 60 * 1000
      const tick = () => {
        const state = models.byKey.get(key)?.state
        if (state !== 'starting' || Date.now() > deadline) resolve()
        else setTimeout(tick, 400)
      }
      tick()
    })
  }

  /** Start models one at a time, waiting for each to settle before the next. */
  async function startSequential(keys: string[]) {
    for (const key of keys) {
      const m = models.byKey.get(key)
      if (!m || m.state === 'ready' || m.state === 'starting') continue
      await runOne(key, 'start')
      await waitUntilNotStarting(key)
    }
  }

  async function runOne(key: string, action: Action, force = false) {
    const name = key.split('::')[0]
    if (action === 'start' && isStartBlocked(key)) {
      toast.warning('一次只能啟動一顆模型', {
        description: `「${startingLlmName()}」正在啟動中，請待其完成後再啟動 ${name}。`,
      })
      return
    }
    try {
      if (action === 'start') {
        await models.start(key, force)
        toast.success(`正在啟動 ${name}`, { description: '等待 /health 通過…' })
      } else {
        await models.stop(key)
        toast.info(`正在停止 ${name}`, { description: '釋放 GPU 資源…' })
      }
    } catch (e) {
      // A VRAM pre-flight block (409 mentioning force) gets a one-click override.
      if (action === 'start' && e instanceof ApiError && e.status === 409 && /force=true/i.test(e.message)) {
        toast.warning(`${name}：VRAM 不足`, {
          description: e.message,
          duration: 10000,
          action: { label: '強制啟動', onClick: () => void runOne(key, 'start', true) },
        })
        return
      }
      const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e)
      toast.error(`${action === 'start' ? '啟動' : '停止'} ${name} 失敗`, { description: msg })
    }
  }

  function execute(keys: string[], action: Action) {
    // Stops can fire in parallel; starts are serialised so two model weights
    // never load at once.
    if (action === 'stop') {
      for (const key of keys) void runOne(key, 'stop')
      return
    }
    void startSequential(keys)
  }

  async function requestMany(keys: string[], action: Action) {
    if (!keys.length) return
    if (!(await ensureUnlocked())) return
    execute(keys, action)
  }

  function request(key: string, action: Action) {
    void requestMany([key], action)
  }

  return {
    request,
    requestMany,
    isLlmStarting,
    isStartBlocked,
    startingLlmName,
  }
}
