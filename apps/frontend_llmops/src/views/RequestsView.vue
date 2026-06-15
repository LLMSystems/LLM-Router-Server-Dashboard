<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RefreshCw, Search } from '@lucide/vue'
import { api } from '@/lib/api'
import { toast } from '@/lib/toast'
import { formatLatency, formatNumber, formatTime } from '@/lib/utils'
import type { RequestRow } from '@/types/api'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'

const RATE_KEY = 'llmops_cost_per_mtok'

const rows = ref<RequestRow[]>([])
const loading = ref(false)
const query = ref('')
const errorsOnly = ref(false)
const limit = ref(200)
// Blended price per 1M tokens (USD), persisted — turns token counts into cost.
const ratePerMTok = ref<number>(Number(localStorage.getItem(RATE_KEY)) || 0)

async function load() {
  loading.value = true
  try {
    rows.value = await api.getRequests({ limit: limit.value })
  } catch (e) {
    toast.error('無法載入請求紀錄', { description: String(e) })
  } finally {
    loading.value = false
  }
}

function setRate(v: number) {
  ratePerMTok.value = v
  localStorage.setItem(RATE_KEY, String(v))
}

function cost(tokens: number | null): number {
  return tokens && ratePerMTok.value ? (tokens / 1_000_000) * ratePerMTok.value : 0
}
function isError(r: RequestRow): boolean {
  return !!r.error || (r.status_code ?? 0) >= 400
}

const filtered = computed(() =>
  rows.value.filter((r) => {
    if (errorsOnly.value && !isError(r)) return false
    if (query.value) {
      const q = query.value.toLowerCase()
      const hay = `${r.model_key} ${r.path} ${r.api_key_name ?? ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  }),
)

const totals = computed(() => {
  let tokens = 0
  let errors = 0
  for (const r of filtered.value) {
    tokens += r.total_tokens ?? 0
    if (isError(r)) errors++
  }
  const n = filtered.value.length
  return {
    count: n,
    tokens,
    errorRate: n ? (errors / n) * 100 : 0,
    cost: (tokens / 1_000_000) * ratePerMTok.value,
  }
})

onMounted(load)
</script>

<template>
  <div class="space-y-6 p-6">
    <!-- Toolbar -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="relative">
        <Search class="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input v-model="query" placeholder="搜尋模型 / 路徑 / 金鑰…" class="w-64 pl-8" />
      </div>
      <label class="flex items-center gap-1.5 text-sm text-muted-foreground">
        <input v-model="errorsOnly" type="checkbox" class="size-4 accent-[var(--chart-1)]" />僅錯誤
      </label>
      <label class="flex items-center gap-1.5 text-sm text-muted-foreground">
        $/1M tokens
        <Input
          :model-value="ratePerMTok"
          type="number"
          min="0"
          step="0.01"
          class="w-24"
          @update:model-value="setRate(Number($event))"
        />
      </label>
      <div class="ml-auto flex items-center gap-3">
        <select
          v-model.number="limit"
          class="h-9 rounded-md border border-input bg-background/40 px-2 text-sm"
          @change="load"
        >
          <option :value="100">最近 100</option>
          <option :value="200">最近 200</option>
          <option :value="500">最近 500</option>
        </select>
        <Button variant="outline" size="sm" :disabled="loading" @click="load">
          <RefreshCw class="size-3.5" :class="loading && 'animate-spin'" />重新整理
        </Button>
      </div>
    </div>

    <!-- Summary -->
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Card class="p-4 text-center">
        <p class="text-lg font-semibold tabular">{{ formatNumber(totals.count) }}</p>
        <p class="text-xs text-muted-foreground">請求數</p>
      </Card>
      <Card class="p-4 text-center">
        <p class="text-lg font-semibold tabular">{{ formatNumber(totals.tokens, true) }}</p>
        <p class="text-xs text-muted-foreground">總 tokens</p>
      </Card>
      <Card class="p-4 text-center">
        <p class="text-lg font-semibold tabular" :class="totals.errorRate > 0 ? 'text-status-failed' : ''">
          {{ totals.errorRate.toFixed(1) }}%
        </p>
        <p class="text-xs text-muted-foreground">錯誤率</p>
      </Card>
      <Card class="p-4 text-center">
        <p class="text-lg font-semibold tabular">${{ totals.cost.toFixed(4) }}</p>
        <p class="text-xs text-muted-foreground">估算成本</p>
      </Card>
    </div>

    <!-- Table -->
    <Card class="overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border/60 text-xs text-muted-foreground">
            <tr class="[&>th]:px-3 [&>th]:py-2 [&>th]:text-left [&>th]:font-medium">
              <th>時間</th>
              <th>模型</th>
              <th>路徑</th>
              <th class="text-right">狀態</th>
              <th class="text-right">延遲</th>
              <th class="text-right">tokens</th>
              <th class="text-right">成本</th>
              <th>金鑰</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in filtered"
              :key="r.id"
              class="border-b border-border/40 [&>td]:px-3 [&>td]:py-2 hover:bg-accent/30"
            >
              <td class="whitespace-nowrap text-muted-foreground tabular">{{ formatTime(r.ts) }}</td>
              <td class="font-mono text-xs">{{ r.model_key }}</td>
              <td class="font-mono text-xs text-muted-foreground">{{ r.path }}</td>
              <td class="text-right tabular" :class="isError(r) ? 'text-status-failed' : 'text-status-ready'">
                {{ r.status_code ?? '—' }}
              </td>
              <td class="text-right tabular">{{ formatLatency(r.latency_ms) }}</td>
              <td class="text-right tabular">{{ r.total_tokens ?? '—' }}</td>
              <td class="text-right tabular text-muted-foreground">
                {{ cost(r.total_tokens) ? `$${cost(r.total_tokens).toFixed(5)}` : '—' }}
              </td>
              <td class="font-mono text-xs text-muted-foreground">{{ r.api_key_name ?? '—' }}</td>
            </tr>
            <tr v-if="!filtered.length">
              <td colspan="8" class="px-3 py-10 text-center text-sm text-muted-foreground">
                {{ loading ? '載入中…' : '尚無請求紀錄。' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  </div>
</template>
