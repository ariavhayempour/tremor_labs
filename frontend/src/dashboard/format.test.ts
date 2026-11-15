import { expect, test } from 'vitest'
import type { CheckOut, TestOut } from '../api/types'
import { dailyBars, dayLabel, doseBars, handSeries, testsDone, windowStart } from './format'
const NOW = new Date(2026, 10, 14, 15, 0)
const tap = (hand: 'left' | 'right', rate: number, status: TestOut['status'] = 'done'): TestOut => ({ id: 1, type: 'tap', hand, status, fail_reason: null, result: status === 'done' ? { taps_per_sec: rate } as TestOut['result'] : null })
const check = (at: Date, tests: TestOut[]): CheckOut => ({ id: 1, created_at: at.toISOString(), minutes_since_dose: null, notes: null, dose_id: null, tests })

test('window starts at local midnight days-1 ago', () => {
  expect(windowStart(1, NOW)).toEqual(new Date(2026, 10, 14))
  expect(windowStart(14, NOW)).toEqual(new Date(2026, 10, 1))
})
test('day labels use the local calendar date, not UTC', () => {
  expect(dayLabel('2026-11-14')).toBe('Nov 14')
  expect(dailyBars([{ date: '2026-11-01', mean_rest: null, count: 3 }])).toEqual([{ day: 'Nov 1', count: 3 }])
})
test('dose bars sit at bin centres', () => {
  expect(doseBars([{ start_h: 1, mean: 0.07, count: 5 }])).toEqual([{ h: 1.25, label: '1–1.5 h', mean: 0.07, count: 5 }])
})
test('hand series averages done taps per hand per local day', () => {
  const series = handSeries([
    check(new Date(2026, 10, 14, 9), [tap('left', 3), tap('right', 4), tap('right', 2, 'failed')]),
    check(new Date(2026, 10, 14, 13), [tap('left', 5)]),
  ], 2, NOW)
  expect(series).toEqual([{ day: 'Nov 13', left: null, right: null }, { day: 'Nov 14', left: 4, right: 4 }])
})
test('tests done counts distinct done test types', () => {
  expect(testsDone(check(NOW, [tap('left', 3), tap('right', 4), tap('left', 1, 'failed')]))).toBe(1)
})
