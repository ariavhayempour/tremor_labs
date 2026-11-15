import type { Health, PositionMsg } from '../api/types'
import { copy } from '../copy'
const t = copy.sensorCheck

/** Problems with the sensor link, in the order a person should fix them; empty when ready. */
export function healthProblems(h: Health): string[] {
  if (!h.connected) return [t.boardOffline]
  return [...(h.sensors_detected.movement ? [] : [t.missingMovement]), ...(h.sensors_detected.distance ? [] : [t.missingDistance])]
}
export function bandMessage(p: PositionMsg | null): string {
  if (!p || p.tof_mm === null) return t.noReading
  if (p.tof_mm < p.band[0]) return t.tooLow
  if (p.tof_mm > p.band[1]) return t.tooHigh
  return t.inBand
}
