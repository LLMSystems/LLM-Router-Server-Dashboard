import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useModelsStore } from '@/stores/models'
import type { ModelView } from '@/types/api'

function mv(key: string, kind: ModelView['kind'], state: ModelView['state']): ModelView {
  return { key, kind, state } as ModelView
}

describe('useModelsStore derived state', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('computes counts, byKey, and kind filters', () => {
    const s = useModelsStore()
    s.models = [
      mv('Qwen::a', 'llm', 'ready'),
      mv('Qwen::b', 'llm', 'failed'),
      mv('embedding::default', 'embedding', 'ready'),
    ]
    expect(s.total).toBe(3)
    expect(s.readyCount).toBe(2)
    expect(s.counts.failed).toBe(1)
    expect(s.hasFailures).toBe(true)
    expect(s.llms.map((m) => m.key)).toEqual(['Qwen::a', 'Qwen::b'])
    expect(s.embeddings.map((m) => m.key)).toEqual(['embedding::default'])
    expect(s.byKey.get('Qwen::b')?.state).toBe('failed')
  })

  it('has no failures when all healthy', () => {
    const s = useModelsStore()
    s.models = [mv('M::a', 'llm', 'ready'), mv('M::b', 'llm', 'stopped')]
    expect(s.hasFailures).toBe(false)
    expect(s.readyCount).toBe(1)
  })
})
