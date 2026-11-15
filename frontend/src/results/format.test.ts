import { expect, test } from 'vitest'
import type { Card } from '../api/types'
import { cardBaseline, cardValue, sinceDose } from './format'
const card = (over: Partial<Card>): Card => ({ test: 'rest', metric: 'strength_score', value: 42.4, unit: 'score', baseline_pct: 12.6, baseline_n: 5, status: 'done', ...over })

test('time since dose', () => {
  expect(sinceDose(null)).toBe('No dose logged yet')
  expect(sinceDose(45)).toBe('45 min since your last dose')
  expect(sinceDose(120)).toBe('2 h since your last dose')
  expect(sinceDose(125.4)).toBe('2 h 5 min since your last dose')
  expect(sinceDose(0)).toBe('0 min since your last dose')
})
test('card values by status and unit', () => {
  expect(cardValue(card({}))).toBe('42')
  expect(cardValue(card({ unit: 'mm', value: 3.44 }))).toBe('3.4 mm')
  expect(cardValue(card({ unit: 'taps/s', value: 3.9 }))).toBe('3.9 taps/s')
  expect(cardValue(card({ status: 'failed', value: null }))).toBe('Not recorded')
  expect(cardValue(card({ status: 'missing', value: null }))).toBe('Skipped')
})
test('baseline text', () => {
  expect(cardBaseline(card({}))).toBe('+13% vs your usual')
  expect(cardBaseline(card({ baseline_pct: -8 }))).toBe('-8% vs your usual')
  expect(cardBaseline(card({ baseline_pct: null, baseline_n: 2 }))).toBe('Building your baseline · 2 of 3 earlier checks')
  expect(cardBaseline(card({ status: 'failed' }))).toBe('')
})
