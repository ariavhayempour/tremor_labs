import { expect, test } from 'vitest'
import { afterDose, duration, fmt, fmtMeasure, hourLabel, shortDate, unitAfter } from './format'

test('durations and dose timing read plainly', () => {
  expect(duration(239)).toBe('3 h 59 min')
  expect(duration(60)).toBe('1 h')
  expect(duration(12)).toBe('12 min')
  expect(afterDose(239, 0)).toBe('3 h 59 min after the morning dose')
  expect(afterDose(64, 2, true)).toBe('1 h 4 min after dose')
  expect(afterDose(null, null)).toBe('Before the first dose')
})
test('values keep their precision and units', () => {
  expect(fmt(null, 1)).toBe('—')
  expect(fmtMeasure('restStrength', 0.2)).toBe('0.200')
  expect(unitAfter('rest')).toBe('')
  expect(unitAfter('reach')).toBe(' mm')
  expect(shortDate('2026-11-04')).toBe('Nov 4')
  expect(hourLabel(12)).toBe('12 PM')
  expect(hourLabel(8)).toBe('8 AM')
})
