import type { WsMessage } from './types'
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const numbers = (v: unknown): v is number[] => Array.isArray(v) && v.every(finite)
const nullableNumber = (v: unknown) => v === null || finite(v)
const sensors = (v: unknown) => !!v && typeof v === 'object' && typeof Reflect.get(v, 'movement') === 'boolean' && typeof Reflect.get(v, 'distance') === 'boolean'

/** Validates one /ws frame against the contract; returns null for anything malformed. */
export function parseMessage(raw: string): WsMessage | null {
  let m: unknown
  try { m = JSON.parse(raw) } catch { return null }
  if (!m || typeof m !== 'object') return null
  const o = m as Record<string, unknown>
  switch (o.type) {
    case 'imu':
      return finite(o.t0) && finite(o.fs) && o.fs > 0 && Array.isArray(o.samples) && o.samples.every(r => numbers(r) && r.length === 6) ? m as WsMessage : null
    case 'tof':
      return finite(o.t0) && numbers(o.t) && numbers(o.samples_mm) && o.t.length === o.samples_mm.length ? m as WsMessage : null
    case 'spectrum':
      return numbers(o.freqs) && numbers(o.psd) && o.freqs.length === o.psd.length && nullableNumber(o.peak_hz) ? m as WsMessage : null
    case 'position':
      return nullableNumber(o.tof_mm) && typeof o.in_band === 'boolean' && numbers(o.band) && o.band.length === 2 && finite(o.valid_seconds) ? m as WsMessage : null
    case 'status':
      return typeof o.recording === 'boolean' ? m as WsMessage : null
    case 'source':
      return typeof o.connected === 'boolean' && sensors(o.sensors) ? m as WsMessage : null
    default:
      return null
  }
}
