const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/
/** "8:00, 13:00" → ["08:00", "13:00"]; null if any entry isn't a 24-hour time. */
export function parseTimes(text: string): string[] | null {
  const parts = text.split(',').map(p => p.trim()).filter(Boolean).map(p => /^\d:\d\d$/.test(p) ? `0${p}` : p)
  return parts.every(p => HHMM.test(p)) ? parts : null
}
/** Mirrors the backend rule: 0 <= low < high <= 2000 mm. */
export function parseBand(low: string, high: string): [number, number] | null {
  const lo = Number(low), hi = Number(high)
  return low.trim() && high.trim() && Number.isFinite(lo) && Number.isFinite(hi) && lo >= 0 && lo < hi && hi <= 2000 ? [lo, hi] : null
}
