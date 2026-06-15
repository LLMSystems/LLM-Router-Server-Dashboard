<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ClipboardCheck, ExternalLink, Loader2, Play, Square, Trash2 } from '@lucide/vue'
import { api, ApiError } from '@/lib/api'
import { useModelsStore } from '@/stores/models'
import { useAuth } from '@/composables/useAuth'
import { toast } from '@/lib/toast'
import { formatTime } from '@/lib/utils'
import type { EvalDataset, EvalRequest, EvalResult, EvalRun } from '@/types/api'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Badge from '@/components/ui/Badge.vue'

const models = useModelsStore()
const { ensureUnlocked } = useAuth()

// ---- model picker (shared with the benchmark page) ----
const groups = computed(() => [...new Set(models.llms.map((m) => m.key.split('::')[0] ?? m.key))])
function groupReady(g: string) {
  return models.llms.some((m) => m.key.split('::')[0] === g && m.state === 'ready')
}
const model = ref('')
const name = ref('')
const target = ref<'router' | 'instance'>('router')
const instanceKey = ref('')
const instanceOptions = computed(() =>
  models.llms.filter((m) => m.key.split('::')[0] === model.value).map((m) => m.key),
)
watch(groups, (g) => {
  if (!model.value && g.length) model.value = g.find(groupReady) ?? g[0]!
}, { immediate: true })
watch(model, () => { instanceKey.value = instanceOptions.value[0] ?? '' })

// ---- dataset catalog (grouped by tier) + cached state ----
const catalog = ref<EvalDataset[]>([])
const cachedKeys = ref<Set<string>>(new Set())
const selected = ref<Set<string>>(new Set())
const tiers = computed(() => {
  const out: { tier: string; items: EvalDataset[] }[] = []
  for (const d of catalog.value) {
    let g = out.find((x) => x.tier === d.tier)
    if (!g) out.push((g = { tier: d.tier, items: [] }))
    g.items.push(d)
  }
  return out
})
function toggleDataset(key: string) {
  const s = new Set(selected.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  selected.value = s
}
function toggleTier(items: EvalDataset[]) {
  const s = new Set(selected.value)
  const allOn = items.every((d) => s.has(d.key))
  for (const d of items) {
    if (allOn) s.delete(d.key)
    else s.add(d.key)
  }
  selected.value = s
}

// ---- run config ----
const limit = ref(10) // 0 = full dataset
const repeats = ref(1)
const temperature = ref(0)
const maxTokens = ref(2048)
const launching = ref(false)

async function loadCatalog() {
  try {
    catalog.value = (await api.listEvalDatasets()).datasets
  } catch (e) {
    toast.error('無法讀取評測資料集', { description: String(e) })
  }
  try {
    const cache = await api.getDatasets()
    cachedKeys.value = new Set(cache.datasets.filter((d) => d.cached).map((d) => d.key))
  } catch {
    /* non-fatal: cached badges just won't show */
  }
}

// ---- runs ----
const runs = ref<EvalRun[]>([])
const busy = ref(false)
const selectedId = ref<number | null>(null)
const detail = ref<EvalRun | null>(null)
const result = ref<EvalResult | null>(null)
const log = ref('')
let poll: ReturnType<typeof setInterval> | null = null

const selectedRunning = computed(() => detail.value?.status === 'running')

function parseResult(raw: string | null | undefined): EvalResult | null {
  if (!raw) return null
  try {
    return JSON.parse(raw) as EvalResult
  } catch {
    return null
  }
}
function runDatasets(r: EvalRun): string[] {
  try {
    return JSON.parse(r.datasets) as string[]
  } catch {
    return []
  }
}
function pct(score: number): string {
  return `${(score * 100).toFixed(1)}%`
}

async function loadRuns() {
  try {
    const r = await api.listEval()
    runs.value = r.runs
    busy.value = r.busy
  } catch {
    /* transient */
  }
}

async function select(id: number) {
  selectedId.value = id
  try {
    detail.value = await api.getEval(id)
    result.value = parseResult(detail.value.result)
  } catch (e) {
    toast.error('無法載入結果', { description: String(e) })
  }
  await loadLog()
}

async function loadLog() {
  if (selectedId.value == null) return
  try {
    log.value = (await api.getEvalLog(selectedId.value)).content
  } catch {
    log.value = ''
  }
}

async function launch() {
  if (launching.value) return
  if (!model.value) {
    toast.error('請選擇一個模型')
    return
  }
  if (!selected.value.size) {
    toast.error('請至少選擇一個資料集')
    return
  }
  const req: EvalRequest = {
    model: model.value,
    name: name.value || undefined,
    target: target.value,
    instance_key: target.value === 'instance' ? instanceKey.value : undefined,
    datasets: [...selected.value],
    limit: limit.value > 0 ? limit.value : null,
    repeats: repeats.value,
    temperature: temperature.value,
    max_tokens: maxTokens.value,
  }
  if (!(await ensureUnlocked())) return
  launching.value = true
  try {
    const run = await api.startEval(req)
    toast.success(`已開始評測 #${run.id}`, { description: '可離開此頁，背景持續執行。' })
    await loadRuns()
    await select(run.id)
  } catch (e) {
    toast.error('無法開始評測', { description: e instanceof ApiError ? `${e.status}: ${e.message}` : String(e) })
  } finally {
    launching.value = false
  }
}

async function cancel(id: number) {
  try {
    await api.cancelEval(id)
    toast.info('已要求取消')
    await loadRuns()
  } catch (e) {
    toast.error('取消失敗', { description: String(e) })
  }
}

async function remove(id: number) {
  if (!confirm(`刪除評測 #${id}？`)) return
  try {
    await api.deleteEval(id)
    if (selectedId.value === id) { selectedId.value = null; detail.value = null; result.value = null }
    await loadRuns()
  } catch (e) {
    toast.error('刪除失敗', { description: String(e) })
  }
}

// Re-fetch the selected run's detail once it leaves the running state.
watch(runs, (list) => {
  if (selectedId.value == null) return
  const r = list.find((x) => x.id === selectedId.value)
  if (r && detail.value && r.status !== detail.value.status) void select(r.id)
})

onMounted(() => {
  void loadCatalog()
  void loadRuns()
  poll = setInterval(() => {
    void loadRuns()
    if (selectedRunning.value) void loadLog()
  }, 2500)
})
onBeforeUnmount(() => { if (poll) clearInterval(poll) })

const STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'outline'> = {
  completed: 'default', running: 'secondary', failed: 'outline', cancelled: 'outline',
}
</script>

<template>
  <div class="space-y-6 p-6">
    <div>
      <h1 class="flex items-center gap-2 text-lg font-semibold"><ClipboardCheck class="size-5" />模型評測</h1>
      <p class="mt-0.5 text-sm text-muted-foreground">
        用 evalscope 量模型的「答對率 / 品質」（與壓測的速度不同）。先在
        <RouterLink to="/datasets" class="text-[var(--chart-1)] underline">資料集庫</RouterLink>
        下載資料集，跑評測就不必等。小模型分數偏低屬正常，重點是換模型 / 調參時的比較。
      </p>
    </div>

    <div class="grid gap-6 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
      <!-- Config -->
      <Card class="space-y-4 p-5">
        <div class="space-y-1.5">
          <label class="text-xs font-medium text-muted-foreground">模型</label>
          <select
            v-model="model"
            class="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          >
            <option v-if="!groups.length" disabled value="">尚未設定模型</option>
            <option v-for="g in groups" :key="g" :value="g">
              {{ g }}{{ groupReady(g) ? '' : ' · 離線' }}
            </option>
          </select>
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-medium text-muted-foreground">目標</label>
          <div class="flex gap-1.5">
            <Button size="sm" :variant="target === 'router' ? 'default' : 'outline'" @click="target = 'router'">路由器</Button>
            <Button size="sm" :variant="target === 'instance' ? 'default' : 'outline'" @click="target = 'instance'">直連實例</Button>
          </div>
          <select
            v-if="target === 'instance'"
            v-model="instanceKey"
            class="mt-1.5 w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          >
            <option v-for="k in instanceOptions" :key="k" :value="k">{{ k }}</option>
          </select>
        </div>

        <!-- Dataset multi-select -->
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <label class="text-xs font-medium text-muted-foreground">資料集</label>
            <span class="text-[10px] text-muted-foreground">已選 {{ selected.size }}</span>
          </div>
          <div v-for="t in tiers" :key="t.tier" class="space-y-1">
            <button
              class="text-[11px] font-medium text-muted-foreground hover:text-foreground"
              @click="toggleTier(t.items)"
            >
              {{ t.tier }} ＋
            </button>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="d in t.items"
                :key="d.key"
                class="rounded-md border px-2 py-1 text-xs transition-colors"
                :class="selected.has(d.key)
                  ? 'border-[var(--chart-1)] bg-[var(--chart-1)]/10 text-foreground'
                  : 'border-border text-muted-foreground hover:bg-muted'"
                :title="d.note ? `${d.dataset_id} · ${d.note}` : d.dataset_id"
                @click="toggleDataset(d.key)"
              >
                {{ d.label }}
                <span v-if="cachedKeys.has(d.key)" class="ml-1 text-[var(--chart-1)]">●</span>
              </button>
            </div>
          </div>
          <p class="text-[10px] text-muted-foreground">● = 已快取，未快取的會在執行時下載。</p>
        </div>

        <!-- Params -->
        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1">
            <label class="text-xs font-medium text-muted-foreground">每集樣本數（0=全部）</label>
            <Input v-model.number="limit" type="number" min="0" />
          </div>
          <div class="space-y-1">
            <label class="text-xs font-medium text-muted-foreground">重複次數</label>
            <Input v-model.number="repeats" type="number" min="1" />
          </div>
          <div class="space-y-1">
            <label class="text-xs font-medium text-muted-foreground">溫度</label>
            <Input v-model.number="temperature" type="number" min="0" max="2" step="0.1" />
          </div>
          <div class="space-y-1">
            <label class="text-xs font-medium text-muted-foreground">最大輸出 tokens</label>
            <Input v-model.number="maxTokens" type="number" min="1" />
          </div>
        </div>

        <div class="space-y-1">
          <label class="text-xs font-medium text-muted-foreground">名稱（選填）</label>
          <Input v-model="name" placeholder="例如：Qwen3-0.6B 基線" />
        </div>

        <Button class="w-full" :disabled="launching" @click="launch">
          <Loader2 v-if="launching" class="size-4 animate-spin" />
          <Play v-else class="size-4" />開始評測
        </Button>
        <p v-if="busy" class="text-center text-[11px] text-amber-600">目前有評測在執行，需等它結束。</p>
      </Card>

      <!-- Runs + detail -->
      <div class="min-w-0 space-y-4">
        <!-- Run list -->
        <Card class="overflow-hidden">
          <div class="border-b border-border/60 px-5 py-3 text-sm font-semibold">評測紀錄</div>
          <div v-if="runs.length" class="divide-y divide-border/60">
            <button
              v-for="r in runs"
              :key="r.id"
              class="flex w-full items-center gap-3 px-5 py-2.5 text-left text-sm hover:bg-muted/50"
              :class="selectedId === r.id && 'bg-muted/60'"
              @click="select(r.id)"
            >
              <span class="tabular text-xs text-muted-foreground">#{{ r.id }}</span>
              <Badge :variant="STATUS_VARIANT[r.status] ?? 'outline'">{{ r.status }}</Badge>
              <span class="min-w-0 flex-1 truncate">
                <span class="font-medium">{{ r.name || r.model }}</span>
                <span class="ml-2 text-xs text-muted-foreground">{{ runDatasets(r).join(', ') }}</span>
              </span>
              <span class="shrink-0 text-xs text-muted-foreground">{{ formatTime(r.created_at) }}</span>
              <Square
                v-if="r.status === 'running'"
                class="size-3.5 text-muted-foreground hover:text-status-failed"
                @click.stop="cancel(r.id)"
              />
              <Trash2
                v-else
                class="size-3.5 text-muted-foreground hover:text-status-failed"
                @click.stop="remove(r.id)"
              />
            </button>
          </div>
          <p v-else class="px-5 py-8 text-center text-sm text-muted-foreground">尚無評測紀錄。</p>
        </Card>

        <!-- Selected detail -->
        <Card v-if="detail" class="p-5">
          <div class="mb-3 flex items-center justify-between">
            <div>
              <p class="text-sm font-semibold">{{ detail.name || detail.model }} · #{{ detail.id }}</p>
              <p class="text-xs text-muted-foreground">{{ detail.model }} · {{ runDatasets(detail).join(', ') }}</p>
            </div>
            <a
              v-if="detail.status === 'completed'"
              :href="api.evalReportUrl(detail.id)"
              target="_blank"
              class="flex items-center gap-1 text-xs text-[var(--chart-1)] hover:underline"
            >
              完整報告 <ExternalLink class="size-3" />
            </a>
          </div>

          <div v-if="detail.status === 'running'" class="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 class="size-4 animate-spin" />評測執行中…（可離開此頁）
          </div>
          <div v-else-if="detail.status === 'failed'" class="text-sm text-status-failed">
            失敗：{{ detail.error }}
          </div>

          <!-- Scores -->
          <table v-if="result?.datasets.length" class="w-full text-sm">
            <thead>
              <tr class="border-b border-border/60 text-left text-xs text-muted-foreground">
                <th class="py-1.5">資料集</th>
                <th class="py-1.5">指標</th>
                <th class="py-1.5 text-right">樣本</th>
                <th class="py-1.5 text-right">分數</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in result.datasets" :key="d.dataset" class="border-b border-border/40">
                <td class="py-1.5 font-medium">{{ d.pretty }}</td>
                <td class="py-1.5 text-xs text-muted-foreground">
                  {{ d.metrics.map((m) => m.name).join(', ') }}
                </td>
                <td class="py-1.5 text-right tabular text-muted-foreground">{{ d.num }}</td>
                <td class="py-1.5 text-right tabular font-semibold">{{ pct(d.score) }}</td>
              </tr>
            </tbody>
          </table>

          <!-- Log -->
          <details class="mt-4" :open="detail.status !== 'completed'">
            <summary class="cursor-pointer text-xs text-muted-foreground">執行日誌</summary>
            <pre class="mt-2 max-h-64 overflow-auto rounded-md bg-muted/60 p-3 text-[11px] leading-relaxed">{{ log || '（無日誌）' }}</pre>
          </details>
        </Card>
      </div>
    </div>
  </div>
</template>
