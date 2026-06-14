<script setup lang="ts">
import { ref, watch } from 'vue'
import { Lock } from '@lucide/vue'
import Dialog from '@/components/ui/Dialog.vue'
import Input from '@/components/ui/Input.vue'
import Button from '@/components/ui/Button.vue'
import { useAuth } from '@/composables/useAuth'

const { dialogOpen, submitToken, cancel } = useAuth()
const token = ref('')
const error = ref(false)
const busy = ref(false)

watch(dialogOpen, (open) => {
  if (open) {
    token.value = ''
    error.value = false
  }
})

async function confirm() {
  if (!token.value || busy.value) return
  busy.value = true
  error.value = false
  try {
    if (!(await submitToken(token.value))) error.value = true
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Dialog v-model:open="dialogOpen" title="管理員驗證" @update:open="(v) => !v && cancel()">
    <div class="space-y-4">
      <p class="flex items-center gap-2 text-sm text-muted-foreground">
        <Lock class="size-4" />
        <span>此操作需要管理員權杖（後端 <span class="font-mono">LLMOPS_ADMIN_TOKEN</span>）。</span>
      </p>
      <div>
        <Input
          v-model="token"
          type="password"
          placeholder="管理員權杖"
          :class="error ? 'border-status-failed focus-visible:ring-status-failed' : ''"
          @keydown.enter="confirm"
        />
        <p v-if="error" class="mt-1.5 text-xs text-status-failed">權杖無效。</p>
      </div>
      <div class="flex justify-end gap-2">
        <Button variant="ghost" @click="cancel">取消</Button>
        <Button :disabled="busy || !token" @click="confirm">確認</Button>
      </div>
    </div>
  </Dialog>
</template>
