export interface HistoryEntry { id: string; at: string; seconds: number; source: 'sample' | 'demo' }
export interface Profile { name: string; email: string }
export interface Preferences { hand: string; reminders: boolean }
export const historyKey = 'tremor-history-v1'
function readObject(key: string): Record<string, unknown> {
  try { const value: unknown = JSON.parse(localStorage.getItem(key) ?? 'null'); return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {} } catch { return {} }
}
export function readProfile(): Profile { const value = readObject('tremor-profile'); return { name: typeof value.name === 'string' ? value.name : '', email: typeof value.email === 'string' ? value.email : '' } }
export function readPreferences(): Preferences { const value = readObject('tremor-preferences'); return { hand: value.hand === 'left' ? 'left' : 'right', reminders: value.reminders !== false } }
export function saveLocal(key: string, value: unknown): boolean { try { localStorage.setItem(key, JSON.stringify(value)); return true } catch { return false } }
export function sampleHistory(): HistoryEntry[] {
  return Array.from({ length: 14 }, (_, day) => {
    const count = day % 4 === 0 ? 2 : 3
    return Array.from({ length: count }, (_, check) => {
      const date = new Date(); date.setDate(date.getDate() - (13 - day)); date.setHours(8 + check * 4, 0, 0, 0)
      return { id: `sample-${day}-${check}`, at: date.toISOString(), seconds: 120, source: 'sample' as const }
    })
  }).flat().sort((a, b) => b.at.localeCompare(a.at))
}
export function readHistory(): HistoryEntry[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(historyKey) ?? 'null')
    if (Array.isArray(value) && value.every(v => v && typeof v === 'object' && typeof v.id === 'string' && typeof v.at === 'string' && Number.isFinite(Date.parse(v.at)) && typeof v.seconds === 'number' && ['sample', 'demo'].includes(v.source))) return value as HistoryEntry[]
  } catch { /* Use the sample history if saved history cannot be read. */ }
  return sampleHistory()
}
export function recordCompletedCheck() {
  try {
    if (sessionStorage.getItem('tremor-history-recorded')) return
    const entry: HistoryEntry = { id: `demo-${Date.now()}`, at: new Date().toISOString(), seconds: 98, source: 'demo' }
    if (saveLocal(historyKey, [entry, ...readHistory()])) sessionStorage.setItem('tremor-history-recorded', '1')
  } catch { /* A completed check remains visible in its summary if storage is unavailable. */ }
}
export const dateLabel = (at: string) => new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(at))
export const timeLabel = (at: string) => new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(new Date(at))
export function dailyCounts(history: HistoryEntry[], days = 7) {
  return Array.from({ length: days }, (_, i) => {
    const day = new Date(); day.setDate(day.getDate() - (days - 1 - i))
    const label = dateLabel(day.toISOString())
    return { day: label, count: history.filter(record => dateLabel(record.at) === label).length }
  })
}
