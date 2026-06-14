<script setup lang="ts">
import { ref } from 'vue'
import { Check, Copy } from '@lucide/vue'
import { toast } from '@/lib/toast'

const props = defineProps<{ code: string }>()
const copied = ref(false)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    toast.error('複製失敗')
  }
}
</script>

<template>
  <div class="group relative">
    <button
      class="absolute right-2 top-2 flex items-center gap-1 rounded-md border border-border/60 bg-card/80 px-2 py-1 text-[11px] text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
      @click="copy"
    >
      <Check v-if="copied" class="size-3.5 text-status-ready" />
      <Copy v-else class="size-3.5" />
      {{ copied ? '已複製' : '複製' }}
    </button>
    <pre
      class="overflow-x-auto rounded-lg border border-border/60 bg-black/40 p-4 font-mono text-xs leading-relaxed text-foreground/90"
    ><code>{{ code }}</code></pre>
  </div>
</template>
