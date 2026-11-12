import { describe, expect, it } from 'vitest'

import { formatCurrency, formatDay, formatDuration, initials, localDateOf, titleCase } from './format'

describe('format helpers', () => {
  it('formats money in the configured currency', () => {
    expect(formatCurrency(1234.5)).toBe('₹1,234.50')
    expect(formatCurrency(null)).toBe('₹0.00')
  })

  it('formats calendar dates without time-zone drift', () => {
    expect(formatDay('2026-11-12')).toBe('12 Nov')
  })

  it('converts timestamps to the hospital-local calendar date', () => {
    // 20:00 UTC on 11 Nov is already 12 Nov in India (UTC+05:30).
    expect(localDateOf('2026-11-11T20:00:00Z')).toBe('2026-11-12')
  })

  it('humanises enum values', () => {
    expect(titleCase('no_show')).toBe('No show')
    expect(titleCase('partially_paid')).toBe('Partially paid')
  })

  it('builds initials and ignores the Dr. prefix', () => {
    expect(initials('Dr. Arjun Mehta')).toBe('AM')
    expect(initials('Priya')).toBe('P')
  })

  it('formats uptime durations', () => {
    expect(formatDuration(59)).toBe('0m 59s')
    expect(formatDuration(3_700)).toBe('1h 1m')
    expect(formatDuration(90_000)).toBe('1d 1h')
  })
})
