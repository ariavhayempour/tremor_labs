import { describe, expect, test } from 'vitest'
import type { CheckOut, ResultOut } from '../api/types'
import { buildDays, byHand, checkHand, compare, doseBins, firstWeek, lastDays, MEASURES, mean, position, quantile, usualRange } from './model'
import { sampleTrends } from './sampleTrends'
import { forHand } from './useTrendsData'

const NOW = new Date(2026, 10, 14, 22, 0)
const blank: ResultOut = { peak_hz: null, strength_ms2: null, strength_score: null, tremor_detected: null, valid_seconds: null, smoothness: null, wobble_ratio: null, taps_per_sec: null, tap_amplitude: null, amplitude_decrement: null, rhythm_cv: null, details: {} }
const check = (id: number, at: Date, score: number, ms2: number, minutes: number | null): CheckOut => ({
  id, created_at: at.toISOString(), minutes_since_dose: minutes, notes: null, dose_id: null,
  tests: [{ id, type: 'rest', hand: 'right', status: 'done', fail_reason: null, result: { ...blank, strength_score: score, strength_ms2: ms2 } }],
})

describe('sample data', () => {
  test('is deterministic, newest first, and never in the future', () => {
    const a = sampleTrends(NOW), b = sampleTrends(NOW)
    expect(a).toEqual(b)
    expect(a.checks.length).toBeGreaterThanOrEqual(14 * 3 - 4)
    expect(a.checks[0].created_at >= a.checks.at(-1)!.created_at).toBe(true)
    expect(a.checks.every(c => new Date(c.created_at) <= NOW)).toBe(true)
    expect(a.doses).toHaveLength(14 * 3)
  })
  test('every check has all four tests on one hand', () => {
    const { checks } = sampleTrends(NOW)
    for (const c of checks) {
      expect(c.tests.map(x => x.type)).toEqual(['rest', 'posture', 'reach', 'tap'])
      expect(new Set(c.tests.map(x => x.hand)).size).toBe(1)
      for (const key of ['rest', 'posture', 'reach', 'tap'] as const) expect(MEASURES[key].get(c)).not.toBeNull()
      expect(MEASURES[checkHand(c) === 'left' ? 'tapR' : 'tapL'].get(c)).toBeNull()
    }
  })
  test('both hands are checked about equally', () => {
    const { checks } = sampleTrends(NOW)
    const left = byHand(checks, 'left').length, right = byHand(checks, 'right').length
    expect(left + right).toBe(checks.length)
    expect(Math.abs(left - right)).toBeLessThanOrEqual(1)
    expect(byHand(checks, 'both')).toBe(checks)
  })
})

describe('aggregation', () => {
  test('mean ignores nulls and quantile interpolates', () => {
    expect(mean([1, null, 3])).toBe(2)
    expect(mean([null])).toBeNull()
    expect(quantile([1, 2, 3, 4], 0.5)).toBe(2.5)
  })
  test('buildDays covers every day in the window, oldest first', () => {
    const days = buildDays(sampleTrends(NOW).checks, 7, NOW)
    expect(days).toHaveLength(7)
    expect(days[0].date < days[6].date).toBe(true)
    expect(days[6].date).toBe('2026-11-14')
  })
  test('first week and last 3 days split by calendar day', () => {
    const checks = [check(1, new Date(2026, 10, 1, 9), 10, 0.1, 60), check(2, new Date(2026, 10, 7, 23), 20, 0.1, 60), check(3, new Date(2026, 10, 8, 9), 30, 0.1, 60), check(4, new Date(2026, 10, 12, 9), 40, 0.1, 60)]
    expect(firstWeek(checks).map(c => c.id)).toEqual([1, 2])
    expect(lastDays(checks, NOW).map(c => c.id)).toEqual([4])
  })
  test('usual range needs 3 reference checks', () => {
    const at = new Date(2026, 10, 1, 9)
    expect(usualRange([check(1, at, 10, 0.1, 0), check(2, at, 20, 0.1, 0)], 'rest')).toBeNull()
    expect(usualRange([check(1, at, 10, 0.1, 0), check(2, at, 20, 0.1, 0), check(3, at, 30, 0.1, 0)], 'rest')).toEqual({ lo: 15, hi: 25, n: 3 })
  })
  test('compare uses a 10% band and handles negative references', () => {
    expect(compare(105, 100)).toBe('same')
    expect(compare(120, 100)).toBe('higher')
    expect(compare(-12, -10)).toBe('lower')
    expect(compare(5, null)).toBeNull()
    expect(position(50, { lo: 20, hi: 40, n: 5 })).toBe('above')
    expect(position(30, null)).toBeNull()
  })
  test('dose bins are half-hour wide and find when tremor rises again', () => {
    const at = new Date(2026, 10, 1, 9)
    const checks = [0.2, 0.3, 1.1, 1.2, 1.4, 3.1, 3.2, 3.3].map((h, i) => check(i, at, 0, h < 1 ? 0.2 : h < 3 ? 0.04 : 0.4, h * 60))
    const { bins, returnsAfter } = doseBins(checks)
    expect(bins.map(b => [b.start_h, b.count])).toEqual([[0, 2], [1, 3], [3, 3]])
    expect(returnsAfter).toBe(3)
  })
})

describe('hand filter', () => {
  test('keeps one hand and recomputes that hand\'s first week and recent checks', () => {
    const at = (d: number) => new Date(2026, 10, d, 9)
    const withHand = (c: CheckOut, hand: 'left' | 'right'): CheckOut => ({ ...c, tests: c.tests.map(x => ({ ...x, hand })) })
    const checks = [withHand(check(1, at(1), 10, 0.1, 60), 'left'), withHand(check(2, at(5), 20, 0.1, 60), 'right'), withHand(check(3, at(13), 30, 0.1, 60), 'left')]
    const data = { now: NOW, checks, doses: [], reference: firstWeek(checks), recent: lastDays(checks, NOW), sample: true }
    expect(forHand(data, 'both')).toBe(data)
    const right = forHand(data, 'right')
    expect(right.checks.map(c => c.id)).toEqual([2])
    expect(right.reference.map(c => c.id)).toEqual([2])
    expect(right.recent).toEqual([])
    expect(forHand(data, 'left').recent.map(c => c.id)).toEqual([3])
  })
})
