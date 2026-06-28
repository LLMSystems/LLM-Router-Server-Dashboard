<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Download, History, Loader2, Lock, RotateCcw, ShieldAlert, Upload, X } from '@lucide/vue'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/composables/useAuth'
import { toast } from '@/lib/toast'
import { formatTime } from '@/lib/utils'
import type { ConfigDiff, ConfigVersion, ImportSummary } from '@/types/api'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'
import UserAvatar from '@/components/UserAvatar.vue'

const { t } = useI18n()
const { authEnabled, isAdmin, ensureUnlocked, refreshStatus } = useAuth()

const rows = ref<ConfigVersion[]>([])
const loading = ref(false)
const locked = ref(false)
const denied = ref(false)
const busy = ref(false)
const PAGE = 50
const reachedEnd = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const diff = ref<(ConfigDiff & { id: number }) | null>(null)

const roleVariant = (r: string | null) =>
  r === 'admin' ? 'ready' : r === 'operator' ? 'starting' : 'muted'

function summarize(s: ImportSummary): string {
  const parts: string[] = []
  if (s.added.length) parts.push(t('config.nAdded', { n: s.added.length }))
  if (s.removed.length) parts.push(t('config.nRemoved', { n: s.removed.length }))
  if (s.changed.length) parts.push(t('config.nChanged', { n: s.changed.length }))
  return parts.length ? parts.join(', ') : t('config.noChange')
}

async function load() {
  if (!(await ensureUnlocked())) {
    locked.value = true
    return
  }
  locked.value = false
  loading.value = true
  try {
    const { versions } = await api.listConfigVersions()
    rows.value = versions
    reachedEnd.value = versions.length < PAGE
    denied.value = false
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) locked.value = true
    else if (e instanceof ApiError && e.status === 403) denied.value = true
    else toast.error(t('config.loadFailed'), { description: String(e) })
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  const last = rows.value[rows.value.length - 1]
  if (!last || loading.value) return
  loading.value = true
  try {
    const { versions } = await api.listConfigVersions(last.id)
    rows.value = rows.value.concat(versions)
    reachedEnd.value = versions.length < PAGE
  } catch (e) {
    toast.error(t('config.loadFailed'), { description: String(e) })
  } finally {
    loading.value = false
  }
}

async function exportConfig() {
  if (!(await ensureUnlocked())) return
  try {
    const data = await api.exportConfig()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
    a.href = url
    a.download = `vllmux-config-${stamp}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    toast.error(t('config.exportFailed'), { description: String(e) })
  }
}

function pickFile() {
  fileInput.value?.click()
}

async function onFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  ;(e.target as HTMLInputElement).value = '' // allow re-picking the same file
  if (!file || !(await ensureUnlocked())) return
  let parsed: unknown
  try {
    parsed = JSON.parse(await file.text())
  } catch {
    toast.error(t('config.badFile'))
    return
  }
  // Accept either a full export wrapper or a bare overlay.
  const payload =
    parsed && typeof parsed === 'object' && 'overlay' in (parsed as Record<string, unknown>)
      ? (parsed as { overlay: unknown }).overlay
      : parsed
  await runImport(payload)
}

async function runImport(overlay: unknown, force = false) {
  busy.value = true
  try {
    const res = await api.importConfig(overlay, force)
    toast.success(t('config.imported'), { description: summarize(res) })
    await load()
  } catch (e) {
    if (e instanceof ApiError && e.status === 409 && !force) {
      if (confirm(t('config.runningConfirm', { detail: e.message }))) {
        await runImport(overlay, true)
      }
    } else {
      toast.error(t('config.importFailed'), {
        description: e instanceof ApiError ? `${e.status}: ${e.message}` : String(e),
      })
    }
  } finally {
    busy.value = false
  }
}

async function rollback(v: ConfigVersion, force = false) {
  if (!(await ensureUnlocked())) return
  if (!force && !confirm(t('config.rollbackConfirm', { id: v.id }))) return
  busy.value = true
  try {
    const res = await api.rollbackConfigVersion(v.id, force)
    toast.success(t('config.rolledBack', { id: v.id }), { description: summarize(res) })
    await load()
  } catch (e) {
    if (e instanceof ApiError && e.status === 409 && !force) {
      if (confirm(t('config.runningConfirm', { detail: e.message }))) await rollback(v, true)
    } else {
      toast.error(t('config.rollbackFailed'), {
        description: e instanceof ApiError ? `${e.status}: ${e.message}` : String(e),
      })
    }
  } finally {
    busy.value = false
  }
}

async function showDiff(v: ConfigVersion) {
  try {
    const d = await api.diffConfigVersion(v.id)
    diff.value = { ...d, id: v.id }
  } catch (e) {
    toast.error(t('config.diffFailed'), { description: String(e) })
  }
}

const hasRows = computed(() => rows.value.length > 0)

onMounted(async () => {
  await refreshStatus()
  await load()
})
</script>

<template>
  <div class="space-y-6 p-6">
    <input ref="fileInput" type="file" accept="application/json,.json" class="hidden" @change="onFile" />
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="flex items-center gap-2 text-lg font-semibold"><History class="size-5" />{{ $t('config.title') }}</h1>
        <p class="mt-0.5 text-sm text-muted-foreground">{{ $t('config.description') }}</p>
      </div>
      <div class="flex items-center gap-2">
        <Button size="sm" variant="outline" @click="exportConfig">
          <Download class="size-4" />{{ $t('config.export') }}
        </Button>
        <Button v-if="isAdmin || authEnabled === false" size="sm" :disabled="busy" @click="pickFile">
          <Loader2 v-if="busy" class="size-4 animate-spin" /><Upload v-else class="size-4" />{{ $t('config.import') }}
        </Button>
      </div>
    </div>

    <Card v-if="denied" class="flex flex-col items-center gap-3 p-10 text-center">
      <ShieldAlert class="size-8 text-status-failed" />
      <p class="text-sm text-muted-foreground">{{ $t('config.denied') }}</p>
    </Card>

    <Card v-else-if="locked" class="flex flex-col items-center gap-3 p-10 text-center">
      <Lock class="size-8 text-muted-foreground" />
      <p class="text-sm text-muted-foreground">{{ $t('config.locked') }}</p>
      <Button size="sm" @click="load">{{ $t('config.unlock') }}</Button>
    </Card>

    <Card v-else class="overflow-hidden">
      <div class="flex items-center justify-between border-b border-border/60 px-5 py-3">
        <p class="text-sm font-semibold">{{ $t('config.history') }}</p>
        <Loader2 v-if="loading" class="size-4 animate-spin text-muted-foreground" />
      </div>
      <table v-if="hasRows" class="w-full text-sm">
        <thead class="border-b border-border/60 text-left text-xs text-muted-foreground">
          <tr>
            <th class="px-4 py-2.5 font-medium">{{ $t('config.colTime') }}</th>
            <th class="px-4 py-2.5 font-medium">{{ $t('config.colActor') }}</th>
            <th class="px-4 py-2.5 font-medium">{{ $t('config.colSummary') }}</th>
            <th class="px-4 py-2.5 text-right font-medium">{{ $t('config.colActions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border/50">
          <tr v-for="r in rows" :key="r.id" class="hover:bg-muted/30">
            <td class="whitespace-nowrap px-4 py-2 text-xs text-muted-foreground">
              {{ formatTime(r.ts) }}
              <Badge v-if="r.is_current" variant="ready" class="ml-1">{{ $t('config.current') }}</Badge>
            </td>
            <td class="px-4 py-2">
              <div class="flex items-center gap-2">
                <UserAvatar :seed="r.actor || 'system'" :size="24" />
                <div class="leading-tight">
                  <span class="text-xs font-medium">{{ r.actor || 'system' }}</span>
                  <Badge v-if="r.role" :variant="roleVariant(r.role)" class="ml-1 text-[10px]">{{ r.role }}</Badge>
                </div>
              </div>
            </td>
            <td class="px-4 py-2 font-mono text-[11px] text-muted-foreground">{{ r.summary || '—' }}</td>
            <td class="px-4 py-2">
              <div class="flex items-center justify-end gap-1">
                <Button size="sm" variant="ghost" @click="showDiff(r)">{{ $t('config.diff') }}</Button>
                <Button
                  v-if="isAdmin || authEnabled === false"
                  size="sm"
                  variant="ghost"
                  :disabled="busy || r.is_current"
                  :title="$t('config.rollback')"
                  @click="rollback(r)"
                >
                  <RotateCcw class="size-4" />
                </Button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else-if="!loading" class="px-5 py-10 text-center text-sm text-muted-foreground">{{ $t('config.none') }}</p>
      <div v-if="hasRows" class="flex items-center justify-center border-t border-border/60 px-5 py-3">
        <Button v-if="!reachedEnd" size="sm" variant="outline" :disabled="loading" @click="loadMore">
          <Loader2 v-if="loading" class="size-4 animate-spin" />{{ $t('config.loadMore') }}
        </Button>
        <span v-else class="text-xs text-muted-foreground">{{ $t('config.end') }}</span>
      </div>
    </Card>

    <!-- Diff modal: snapshot vs the current overlay -->
    <div
      v-if="diff"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6"
      @click.self="diff = null"
    >
      <Card class="flex max-h-[80vh] w-full max-w-5xl flex-col overflow-hidden">
        <div class="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <p class="text-sm font-semibold">{{ $t('config.diffTitle', { id: diff.id }) }}</p>
          <Button size="icon-sm" variant="ghost" @click="diff = null"><X class="size-4" /></Button>
        </div>
        <div class="grid flex-1 grid-cols-2 gap-px overflow-hidden bg-border/60">
          <div class="flex flex-col overflow-hidden bg-background">
            <p class="border-b border-border/60 px-3 py-1.5 text-xs text-muted-foreground">{{ diff.from.label }}</p>
            <pre class="flex-1 overflow-auto p-3 font-mono text-[11px] leading-relaxed">{{ diff.from.text }}</pre>
          </div>
          <div class="flex flex-col overflow-hidden bg-background">
            <p class="border-b border-border/60 px-3 py-1.5 text-xs text-muted-foreground">{{ diff.to.label }}</p>
            <pre class="flex-1 overflow-auto p-3 font-mono text-[11px] leading-relaxed">{{ diff.to.text }}</pre>
          </div>
        </div>
      </Card>
    </div>
  </div>
</template>
