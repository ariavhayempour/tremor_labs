import type { Card } from '../api/types'
import { copy } from '../copy'
const r = copy.results

export function sinceDose(minutes: number | null): string {
  if (minutes === null) return r.noDose
  const total = Math.max(0, Math.round(minutes))
  const h = Math.floor(total / 60), m = total % 60
  const parts = [h ? `${h} ${r.hours}` : '', m || !h ? `${m} ${r.minutes}` : ''].filter(Boolean)
  return `${parts.join(' ')} ${r.sinceDose}`
}
export function cardValue(card: Card): string {
  if (card.status === 'missing') return r.skipped
  if (card.status === 'failed' || card.value === null) return r.notRecorded
  const digits = card.unit === 'score' ? 0 : 1
  const unit = r.units[card.unit]
  return unit ? `${card.value.toFixed(digits)} ${unit}` : card.value.toFixed(digits)
}
/** Neutral comparison with the person's own earlier checks; never a judgement. */
export function cardBaseline(card: Card): string {
  if (card.status !== 'done') return ''
  if (card.baseline_pct === null) return `${r.building} · ${Math.min(card.baseline_n, 3)} ${r.baselineOf}`
  const pct = Math.round(card.baseline_pct)
  return `${pct > 0 ? '+' : ''}${pct}% ${r.vsUsual}`
}
