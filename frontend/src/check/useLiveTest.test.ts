import { expect, test } from 'vitest'
import type { PositionMsg } from '../api/types'
import { runProgress, shouldStop } from './useLiveTest'
const at = (valid_seconds: number): PositionMsg => ({ type: 'position', tof_mm: 200, in_band: true, band: [170, 230], valid_seconds })

test('rest runs for 30 wall-clock seconds', () => {
  expect(runProgress('rest', 12, null)).toBe(12)
  expect(shouldStop('rest', 1, 29.9, 29.9)).toBe(false)
  expect(shouldStop('rest', 1, 30, 30)).toBe(true)
})
test('posture counts only in-band seconds, with a wall-clock cap', () => {
  expect(runProgress('posture', 40, at(18))).toBe(18)
  expect(runProgress('posture', 5, null)).toBe(0)
  expect(shouldStop('posture', 1, 40, 18)).toBe(false)
  expect(shouldStop('posture', 1, 40, 30)).toBe(true)
  expect(shouldStop('posture', 1, 75, 18)).toBe(true)
})
test('reach stops only after the third 6-second attempt', () => {
  expect(shouldStop('reach', 1, 6, 6)).toBe(false)
  expect(shouldStop('reach', 3, 5.9, 5.9)).toBe(false)
  expect(shouldStop('reach', 3, 6, 6)).toBe(true)
})
