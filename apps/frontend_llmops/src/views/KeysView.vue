<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Copy, KeyRound, Loader2, Lock, Plus, Trash2 } from '@lucide/vue'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/composables/useAuth'
import { toast } from '@/lib/toast'
import { formatNumber, formatTime } from '@/lib/utils'
import type { ApiKey, CreatedKey } from '@/types/api'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Badge from '@/components/ui/Badge.vue'
import Dialog from '@/components/ui/Dialog.vue'

const { authEnabled, ensureUnlocked, refreshStatus } = useAuth()

const keys = ref<ApiKey[]>([])
const loading = ref(false)
const locked = ref(false)
const newName = ref('')
const newRpm = ref<number | undefined>(undefined)
const creating = ref(false)

// One-time plaintext reveal after creation.
const reveal = ref<CreatedKey | null>(null)
const revealOpen = ref(false)

async function load() {
  if (!(await ensureUnlocked())) {
    locked.value = true
    return
  }
  locked.value = false
  loading.value = true
  try {
    keys.value = await api.listKeys()
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) locked.value = true
    else toast.error('無法載入金鑰', { description: String(e) })
  } finally {
    loading.value = false
  }
}

async function create() {
  const name = newName.value.trim()
  if (!name || creating.value) return
  if (!(await ensureUnlocked())) return
  creating.value = true
  try {
    reveal.value = await api.createKey(name, newRpm.value && newRpm.value > 0 ? newRpm.value : null)
    revealOpen.value = true
    newName.value = ''
    newRpm.value = undefined
    await load()
  } catch (e) {
    toast.error('建立金鑰失敗', { description: e instanceof ApiError ? `${e.status}: ${e.message}` : String(e) })
  } finally {
    creating.value = false
  }
}

async function revoke(k: ApiKey) {
  if (!(await ensureUnlocked())) return
  try {
    await api.revokeKey(k.id)
    toast.success(`已撤銷 ${k.name}`)
    await load()
  } catch (e) {
    toast.error('撤銷失敗', { description: String(e) })
  }
}

async function copyKey() {
  if (!reveal.value) return
  try {
    await navigator.clipboard.writeText(reveal.value.key)
    toast.success('已複製到剪貼簿')
  } catch {
    toast.error('複製失敗，請手動選取')
  }
}

onMounted(async () => {
  await refreshStatus()
  await load()
})
</script>

<template>
  <div class="space-y-6 p-6">
    <div class="flex flex-wrap items-center gap-3">
      <div>
        <h1 class="flex items-center gap-2 text-lg font-semibold"><KeyRound class="size-5" />API 金鑰</h1>
        <p class="mt-0.5 text-sm text-muted-foreground">
          用於向路由器發送推論請求（<span class="font-mono">Authorization: Bearer …</span>）。金鑰只在建立時顯示一次。
        </p>
      </div>
    </div>

    <!-- Auth-disabled notice -->
    <Card
      v-if="authEnabled === false"
      class="border-status-starting/30 bg-status-starting/10 p-4 text-sm text-status-starting"
    >
      後端未設定 <span class="font-mono">LLMOPS_ADMIN_TOKEN</span>，目前驗證為關閉狀態 —
      金鑰可建立，但路由器尚未強制要求金鑰（需設定 <span class="font-mono">LLMOPS_REQUIRE_API_KEY=true</span>）。
    </Card>

    <!-- Locked -->
    <Card v-if="locked" class="flex flex-col items-center gap-3 p-10 text-center">
      <Lock class="size-8 text-muted-foreground" />
      <p class="text-sm text-muted-foreground">需要管理員權杖才能管理金鑰。</p>
      <Button size="sm" @click="load">解鎖</Button>
    </Card>

    <template v-else>
      <!-- Create -->
      <Card class="p-5">
        <p class="mb-3 text-sm font-semibold">建立新金鑰</p>
        <div class="flex items-end gap-2">
          <label class="flex-1">
            <span class="text-xs text-muted-foreground">名稱（用於用量歸屬）</span>
            <Input v-model="newName" placeholder="例如：team-rag、ci-bot" class="mt-1" @keydown.enter="create" />
          </label>
          <label class="w-32">
            <span class="text-xs text-muted-foreground">速率上限（次/分）</span>
            <Input v-model.number="newRpm" type="number" min="1" placeholder="不限" class="mt-1" @keydown.enter="create" />
          </label>
          <Button :disabled="!newName.trim() || creating" @click="create">
            <Loader2 v-if="creating" class="size-4 animate-spin" /><Plus v-else class="size-4" />建立
          </Button>
        </div>
      </Card>

      <!-- List -->
      <Card class="overflow-hidden">
        <div class="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <p class="text-sm font-semibold">已發行金鑰</p>
          <Loader2 v-if="loading" class="size-4 animate-spin text-muted-foreground" />
        </div>
        <div v-if="keys.length" class="divide-y divide-border/60">
          <div v-for="k in keys" :key="k.id" class="flex items-center gap-4 px-5 py-3">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="truncate text-sm font-medium">{{ k.name }}</span>
                <Badge v-if="k.revoked" variant="muted">已撤銷</Badge>
                <Badge v-if="k.rpm_limit" variant="muted" class="tabular">{{ k.rpm_limit }}/分</Badge>
              </div>
              <span class="font-mono text-xs text-muted-foreground">{{ k.prefix }}</span>
            </div>
            <div class="hidden text-right text-xs sm:block">
              <p class="tabular">
                <span class="font-medium text-foreground">{{ formatNumber(k.request_count) }}</span>
                <span class="text-muted-foreground"> 次 · {{ formatNumber(k.total_tokens, true) }} tokens</span>
              </p>
              <p class="text-muted-foreground">
                最後使用：{{ k.usage_last_ts ? formatTime(k.usage_last_ts) : '—' }}
              </p>
            </div>
            <Button
              v-if="!k.revoked"
              size="icon-sm"
              variant="ghost"
              title="撤銷金鑰"
              @click="revoke(k)"
            >
              <Trash2 class="size-4" />
            </Button>
          </div>
        </div>
        <p v-else-if="!loading" class="px-5 py-10 text-center text-sm text-muted-foreground">尚無金鑰。</p>
      </Card>
    </template>

    <!-- One-time reveal -->
    <Dialog v-model:open="revealOpen" title="金鑰已建立">
      <div class="space-y-4">
        <p class="text-sm text-status-failed">
          請立即複製此金鑰，關閉後將無法再次顯示。
        </p>
        <div class="flex items-center gap-2 rounded-lg border border-border/60 bg-background/40 p-3">
          <code class="flex-1 break-all font-mono text-xs">{{ reveal?.key }}</code>
          <Button size="icon-sm" variant="ghost" title="複製" @click="copyKey"><Copy class="size-4" /></Button>
        </div>
        <div class="flex justify-end">
          <Button @click="revealOpen = false">完成</Button>
        </div>
      </div>
    </Dialog>
  </div>
</template>
