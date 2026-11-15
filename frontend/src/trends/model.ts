import type { Bin, CheckOut, DoseOut, Hand, ResultOut, TestType } from '../api/types'
import { localDate, windowStart } from '../dashboard/format'

export type MeasureKey = 'rest' | 'restStrength' | 'restHz' | 'posture' | 'postureHz' | 'held' | 'reach' | 'endWobble' | 'tap' | 'tapL' | 'tapR' | 'sizeL' | 'sizeR' | 'rhythmL' | 'rhythmR'
export type UnitKey = 'score' | 'ms2' | 'hz' | 's' | 'mm' | 'ratio' | 'taps' | 'pct'
export interface Measure { unit: UnitKey; digits: number; get: (c: CheckOut) => number | null }
export interface TrendDay { date: string; checks: CheckOut[] }
export interface Range { lo: number; hi: number; n: number }
export type Change = 'same' | 'higher' | 'lower'

// Values within this fraction of the reference read as "about the same".
const SAME_BAND = 0.1
const MIN_BASELINE = 3
const FIRST_WEEK_DAYS = 7, RECENT_DAYS = 3
const BIN_H = 0.5, BIN_MAX_H = 6, RETURNS_MIN_H = 1, RETURNS_MIN_N = 3

/** The done result for a test type (and hand, for tap), or null. */
export function resultOf(c: CheckOut, type: TestType, hand?: Hand): ResultOut | null {
  return c.tests.find(t => t.type === type && t.status === 'done' && (!hand || t.hand === hand))?.result ?? null
}
const field = (type: TestType, key: keyof Omit<ResultOut, 'details'>, hand?: Hand, scale = 1) =>
  (c: CheckOut) => { const v = resultOf(c, type, hand)?.[key]; return typeof v === 'number' ? v * scale : null }

export const MEASURES: Record<MeasureKey, Measure> = {
  rest: { unit: 'score', digits: 0, get: field('rest', 'strength_score') },
  restStrength: { unit: 'ms2', digits: 3, get: field('rest', 'strength_ms2') },
  restHz: { unit: 'hz', digits: 1, get: field('rest', 'peak_hz') },
  posture: { unit: 'score', digits: 0, get: field('posture', 'strength_score') },
  postureHz: { unit: 'hz', digits: 1, get: field('posture', 'peak_hz') },
  held: { unit: 's', digits: 1, get: field('posture', 'valid_seconds') },
  reach: { unit: 'mm', digits: 1, get: field('reach', 'smoothness') },
  endWobble: { unit: 'ratio', digits: 2, get: field('reach', 'wobble_ratio') },
  tap: { unit: 'taps', digits: 1, get: c => mean([field('tap', 'taps_per_sec', 'left')(c), field('tap', 'taps_per_sec', 'right')(c)]) },
  tapL: { unit: 'taps', digits: 1, get: field('tap', 'taps_per_sec', 'left') },
  tapR: { unit: 'taps', digits: 1, get: field('tap', 'taps_per_sec', 'right') },
  sizeL: { unit: 'pct', digits: 0, get: field('tap', 'amplitude_decrement', 'left', 100) },
  sizeR: { unit: 'pct', digits: 0, get: field('tap', 'amplitude_decrement', 'right', 100) },
  rhythmL: { unit: 'pct', digits: 0, get: field('tap', 'rhythm_cv', 'left', 100) },
  rhythmR: { unit: 'pct', digits: 0, get: field('tap', 'rhythm_cv', 'right', 100) },
}
export const ALL_MEASURES = Object.keys(MEASURES) as MeasureKey[]

const present = (xs: (number | null)[]) => xs.filter((v): v is number => v !== null && Number.isFinite(v))
export function mean(xs: (number | null)[]): number | null { const v = present(xs); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null }
export function quantile(xs: number[], q: number): number {
  const s = [...xs].sort((a, b) => a - b), p = (s.length - 1) * q, lo = Math.floor(p)
  return s[lo] + (s[Math.min(lo + 1, s.length - 1)] - s[lo]) * (p - lo)
}
export const values = (checks: CheckOut[], key: MeasureKey) => present(checks.map(MEASURES[key].get))
export const meanOf = (checks: CheckOut[], key: MeasureKey) => mean(checks.map(MEASURES[key].get))
export const checkDate = (c: CheckOut) => localDate(new Date(c.created_at))
/** Minutes after local midnight. */
export const minuteOfDay = (iso: string) => { const d = new Date(iso); return d.getHours() * 60 + d.getMinutes() }

/** One entry per local day in the window, oldest first; checks within a day oldest first. */
export function buildDays(checks: CheckOut[], days: number, now: Date = new Date()): TrendDay[] {
  const start = windowStart(days, now)
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(start); d.setDate(start.getDate() + i)
    const date = localDate(d)
    return { date, checks: checks.filter(c => checkDate(c) === date).sort((a, b) => a.created_at.localeCompare(b.created_at)) }
  })
}
/** Checks from the first 7 days after the earliest check: the personal reference. */
export function firstWeek(checks: CheckOut[]): CheckOut[] {
  if (!checks.length) return []
  const first = checks.reduce((a, c) => c.created_at < a ? c.created_at : a, checks[0].created_at)
  const end = new Date(first); end.setHours(0, 0, 0, 0); end.setDate(end.getDate() + FIRST_WEEK_DAYS)
  return checks.filter(c => new Date(c.created_at) < end)
}
export function lastDays(checks: CheckOut[], now: Date = new Date(), days = RECENT_DAYS): CheckOut[] {
  const start = windowStart(days, now)
  return checks.filter(c => new Date(c.created_at) >= start)
}
/** Interquartile range of the reference checks; null until there are enough of them. */
export function usualRange(reference: CheckOut[], key: MeasureKey): Range | null {
  const v = values(reference, key)
  return v.length < MIN_BASELINE ? null : { lo: quantile(v, 0.25), hi: quantile(v, 0.75), n: v.length }
}
export function compare(value: number | null, reference: number | null): Change | null {
  if (value === null || reference === null || reference === 0) return null
  const r = (value - reference) / Math.abs(reference)
  return Math.abs(r) < SAME_BAND ? 'same' : r > 0 ? 'higher' : 'lower'
}
export function position(value: number | null, range: Range | null): 'within' | 'above' | 'below' | null {
  if (value === null || !range) return null
  return value > range.hi ? 'above' : value < range.lo ? 'below' : 'within'
}

/** Rest strength (m/s²) binned by hours since dose, matching the backend's dose-response insight. */
export function doseBins(checks: CheckOut[]): { bins: Bin[]; returnsAfter: number | null } {
  const pairs = checks.flatMap(c => { const v = MEASURES.restStrength.get(c); return c.minutes_since_dose === null || v === null ? [] : [{ h: c.minutes_since_dose / 60, v }] })
  const bins: Bin[] = []
  for (let start = 0; start < BIN_MAX_H; start += BIN_H) {
    const xs = pairs.filter(p => p.h >= start && p.h < start + BIN_H).map(p => p.v)
    if (xs.length) bins.push({ start_h: start, mean: xs.reduce((a, b) => a + b, 0) / xs.length, count: xs.length })
  }
  const all = values(checks, 'restStrength')
  const median = all.length ? quantile(all, 0.5) : 0
  const ret = bins.find(b => b.start_h >= RETURNS_MIN_H && b.mean > median && b.count >= RETURNS_MIN_N)
  return { bins, returnsAfter: ret ? ret.start_h : null }
}
export const dosesOn = (doses: DoseOut[], date: string) => doses.filter(d => localDate(new Date(d.taken_at)) === date)
/** Index of the dose slot (morning, midday, evening) a check follows, or null before the first dose. */
export function doseSlot(c: CheckOut, doses: DoseOut[]): number | null {
  const i = dosesOn(doses, checkDate(c)).findIndex(d => d.id === c.dose_id)
  return i < 0 ? null : i
}
