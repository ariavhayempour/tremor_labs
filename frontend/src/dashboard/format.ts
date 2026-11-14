import type { Bin, CheckOut, DayPoint, Hand } from '../api/types'
const MONTH_DAY = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' })

/** Local midnight `days - 1` days before `now`: the start of the backend's insight window. */
export function windowStart(days: number, now: Date = new Date()): Date {
  const d = new Date(now); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - (days - 1)); return d
}
/** 'YYYY-MM-DD' local calendar date → 'Nov 14'. */
export function dayLabel(date: string): string {
  const [y, m, d] = date.split('-').map(Number)
  return MONTH_DAY.format(new Date(y, m - 1, d))
}
export const localDate = (at: Date) => `${at.getFullYear()}-${String(at.getMonth() + 1).padStart(2, '0')}-${String(at.getDate()).padStart(2, '0')}`
export const dailyBars = (daily: DayPoint[]) => daily.map(p => ({ day: dayLabel(p.date), count: p.count }))
export const doseBars = (bins: Bin[]) => bins.map(b => ({ h: b.start_h + 0.25, label: `${b.start_h}–${b.start_h + 0.5} h`, mean: b.mean, count: b.count }))

export interface HandPoint { day: string; left: number | null; right: number | null }
/** Mean done tap rate per hand per local day, oldest first, one entry per day in the window. */
export function handSeries(checks: CheckOut[], days: number, now: Date = new Date()): HandPoint[] {
  const sums = new Map<string, Record<Hand, number[]>>()
  for (const c of checks) {
    const date = localDate(new Date(c.created_at))
    for (const t of c.tests) {
      const rate = t.result?.taps_per_sec
      if (t.type !== 'tap' || t.status !== 'done' || rate == null) continue
      const day = sums.get(date) ?? { left: [], right: [] }
      day[t.hand].push(rate); sums.set(date, day)
    }
  }
  const mean = (v: number[] | undefined) => v && v.length ? v.reduce((a, b) => a + b, 0) / v.length : null
  const start = windowStart(days, now)
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(start); d.setDate(start.getDate() + i)
    const key = localDate(d)
    return { day: dayLabel(key), left: mean(sums.get(key)?.left), right: mean(sums.get(key)?.right) }
  })
}
export const testsDone = (c: CheckOut) => new Set(c.tests.filter(t => t.status === 'done').map(t => t.type)).size
