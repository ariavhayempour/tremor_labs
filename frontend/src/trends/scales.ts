import type { CheckOut } from '../api/types'
import { niceMax } from './chartTheme'
import { values, type MeasureKey } from './model'

const top = (checks: CheckOut[], keys: MeasureKey[], pad: number, step: number, floor = step) => niceMax(Math.max(floor, ...keys.flatMap(k => values(checks, k))) + pad, step)

/** Fixed y ranges from the whole data set, so every chart of a measure shares one scale across views and days. */
export function scales(checks: CheckOut[]) {
  return {
    score: [0, top(checks, ['rest', 'posture'], 5, 10, 50)] as [number, number],
    reach: [0, top(checks, ['reach'], 0.5, 1)] as [number, number],
    endWobble: [0, top(checks, ['endWobble'], 0.2, 0.5)] as [number, number],
    tap: [0, top(checks, ['tapL', 'tapR'], 0.5, 1)] as [number, number],
    size: [Math.min(-20, Math.floor(Math.min(0, ...values(checks, 'sizeL'), ...values(checks, 'sizeR')) / 5) * 5), 0] as [number, number],
    rhythm: [0, top(checks, ['rhythmL', 'rhythmR'], 2, 5)] as [number, number],
    hz: (() => { const v = [...values(checks, 'restHz'), ...values(checks, 'postureHz')]; return v.length ? [Math.floor(Math.min(...v)) - 1, Math.ceil(Math.max(...v)) + 1] : [3, 7] })() as [number, number],
  }
}
export type Scales = ReturnType<typeof scales>
