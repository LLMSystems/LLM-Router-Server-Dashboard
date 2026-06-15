import { describe, expect, it } from 'vitest'
import { formatBytes, formatLatency, formatNumber, formatPercent } from '@/lib/utils'

describe('formatBytes', () => {
  it('scales units and handles nullish', () => {
    expect(formatBytes(0)).toMatch(/0\s*B/)
    expect(formatBytes(1024)).toMatch(/1(\.0)?\s*KB/)
    expect(formatBytes(1024 * 1024)).toMatch(/MB/)
    expect(formatBytes(null)).toBeTypeOf('string')
  })
})

describe('formatLatency', () => {
  it('formats milliseconds', () => {
    expect(formatLatency(12)).toMatch(/12/)
    expect(formatLatency(null)).toBeTypeOf('string')
  })
})

describe('formatNumber', () => {
  it('formats plain and compact', () => {
    expect(formatNumber(1500)).toBe('1,500')
    expect(formatNumber(1500, true)).toMatch(/1\.5K/i)
    expect(formatNumber(null)).toBeTypeOf('string')
  })
})

describe('formatPercent', () => {
  it('appends a percent sign', () => {
    expect(formatPercent(42)).toMatch(/42/)
    expect(formatPercent(42)).toContain('%')
  })
})
