<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    points: { ts: number; value: number }[]
    color?: string
    height?: number
    /** Formats the y-axis max / current value labels. */
    format?: (v: number) => string
  }>(),
  { color: 'var(--chart-1)', height: 150, format: (v: number) => `${Math.round(v)}` },
)

const W = 600
const PAD_T = 12
const PAD_B = 20
const gid = `tc-${Math.random().toString(36).slice(2, 9)}`

const max = computed(() => Math.max(1, ...props.points.map((p) => p.value)))
const tsMin = computed(() => (props.points.length ? props.points[0]!.ts : 0))
const tsMax = computed(() => (props.points.length ? props.points[props.points.length - 1]!.ts : 1))

function x(ts: number): number {
  const span = tsMax.value - tsMin.value || 1
  return ((ts - tsMin.value) / span) * W
}
function y(v: number): number {
  const h = props.height - PAD_T - PAD_B
  return PAD_T + h - (v / max.value) * h
}

const line = computed(() =>
  props.points.map((p) => `${x(p.ts).toFixed(1)},${y(p.value).toFixed(1)}`).join(' '),
)
const area = computed(() => {
  if (props.points.length < 2) return ''
  const base = props.height - PAD_B
  return `M${x(tsMin.value)},${base} L${line.value.replaceAll(' ', ' L')} L${x(tsMax.value)},${base} Z`
})

function clock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="relative">
    <svg
      :viewBox="`0 0 ${W} ${height}`"
      :height="height"
      preserveAspectRatio="none"
      class="w-full"
    >
      <defs>
        <linearGradient :id="gid" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="color" stop-opacity="0.25" />
          <stop offset="100%" :stop-color="color" stop-opacity="0" />
        </linearGradient>
      </defs>

      <!-- gridlines at max / mid / 0 -->
      <line v-for="f in [0, 0.5, 1]" :key="f" :x1="0" :x2="W" :y1="y(max * f)" :y2="y(max * f)"
        stroke="var(--border)" stroke-opacity="0.5" stroke-width="1" vector-effect="non-scaling-stroke" />

      <path v-if="area" :d="area" :fill="`url(#${gid})`" />
      <polyline v-if="points.length > 1" :points="line" fill="none" :stroke="color" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
      <circle v-else-if="points.length === 1" :cx="x(points[0]!.ts)" :cy="y(points[0]!.value)" r="3" :fill="color" />
    </svg>

    <!-- y max label -->
    <span class="absolute left-1 top-0 text-[10px] text-muted-foreground tabular">{{ format(max) }}</span>
    <!-- x range labels -->
    <div v-if="points.length" class="flex justify-between px-1 text-[10px] text-muted-foreground tabular">
      <span>{{ clock(tsMin) }}</span>
      <span>{{ clock(tsMax) }}</span>
    </div>
    <p v-else class="py-6 text-center text-xs text-muted-foreground">No data in range.</p>
  </div>
</template>
