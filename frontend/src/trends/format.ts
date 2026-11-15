import { copy } from '../copy'
import type { Hand } from '../api/types'
import { MEASURES, type MeasureKey } from './model'
const t = copy.trends

const parse = (date: string) => { const [y, m, d] = date.split('-').map(Number); return new Date(y, m - 1, d) }
const dateFmt = (o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-US', o)
const SHORT = dateFmt({ month: 'short', day: 'numeric' }), LONG = dateFmt({ weekday: 'long', month: 'long', day: 'numeric' })
const WEEKDAY = dateFmt({ weekday: 'short' }), DAY = dateFmt({ day: 'numeric' }), CLOCK = dateFmt({ hour: 'numeric', minute: '2-digit' })

/** 'YYYY-MM-DD' → 'Nov 14'. */
export const shortDate = (date: string) => SHORT.format(parse(date))
/** 'YYYY-MM-DD' → 'Wednesday, November 11'. */
export const longDate = (date: string) => LONG.format(parse(date))
export const weekday = (date: string) => WEEKDAY.format(parse(date))
export const dayOfMonth = (date: string) => DAY.format(parse(date))
/** ISO timestamp → local '9:24 PM'. */
export const clock = (iso: string) => CLOCK.format(new Date(iso))
/** Minutes after midnight → '9:24 PM'. */
export const clockOfMinute = (minute: number) => { const d = new Date(2000, 0, 1); d.setMinutes(Math.round(minute)); return CLOCK.format(d) }
export const hourLabel = (h: number) => `${((h + 11) % 12) + 1} ${h >= 12 ? 'PM' : 'AM'}`

/** A measured value with its fixed precision, or an em dash when missing. */
export const fmt = (v: number | null | undefined, digits: number) => v === null || v === undefined ? '—' : v.toFixed(digits)
export const fmtMeasure = (key: MeasureKey, v: number | null) => fmt(v, MEASURES[key].digits)
export const unitOf = (key: MeasureKey) => t.units[MEASURES[key].unit]
/** Unit to print after a value; scores read as bare numbers. */
export const unitAfter = (key: MeasureKey) => MEASURES[key].unit === 'score' ? '' : ` ${unitOf(key)}`

export const handName = (hand: Hand | null) => hand === 'left' ? t.left : hand === 'right' ? t.right : '—'
/** Minutes → '3 h 59 min'. */
export function duration(minutes: number): string {
  const total = Math.max(0, Math.round(minutes)), h = Math.floor(total / 60), m = total % 60
  return h ? `${h} h${m ? ` ${m} min` : ''}` : `${m} min`
}
export function afterDose(minutes: number | null, slot: number | null, short = false): string {
  if (minutes === null) return short ? t.beforeDoseShort : t.beforeDose
  if (short || slot === null) return `${duration(minutes)} ${t.afterDose}`
  return `${duration(minutes)} ${t.afterThe} ${t.slots[slot] ?? ''} ${t.doseWord}`.replace('  ', ' ')
}
