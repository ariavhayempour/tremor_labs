import type { TapFrame } from '../api/types'
interface Point { x: number; y: number }
export function tapLandmarks(points?: Point[]): TapFrame['lm'] {
  if (!points || [0, 4, 8, 9].some(i => !points[i] || !Number.isFinite(points[i].x) || !Number.isFinite(points[i].y))) return null
  return [0, 4, 8, 9].map(i => [points[i].x, points[i].y])
}
export function opening(lm: TapFrame['lm']): number | null {
  if (!lm) return null
  const distance = (a: number, b: number) => Math.hypot(lm[a][0] - lm[b][0], lm[a][1] - lm[b][1])
  const scale = distance(0, 3)
  return scale > 1e-6 ? distance(1, 2) / scale : null
}
/** UI feedback only; the backend performs authoritative tap analysis. */
export class LiveTapCounter {
  count = 0
  private open = false
  push(ratio: number | null) {
    if (ratio === null) this.open = false
    else if (ratio > 0.5) this.open = true
    else if (ratio < 0.25 && this.open) { this.count++; this.open = false }
    return this.count
  }
}
