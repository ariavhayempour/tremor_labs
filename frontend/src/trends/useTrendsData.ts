import { useMemo, useState } from 'react'
import type { CheckOut, DoseOut } from '../api/types'
import type { HandFilter } from './model'
import { byHand, firstWeek, lastDays } from './model'
import { sampleTrends } from './sampleTrends'

export interface TrendsData { now: Date; checks: CheckOut[]; doses: DoseOut[]; reference: CheckOut[]; recent: CheckOut[]; sample: boolean }
const SAMPLE_DAYS = 14

/** The trends screen's data. Sample checks for now; they use the same shapes as `GET /api/checks` and `GET /api/doses`. */
export function useTrendsData(): TrendsData {
  const [now] = useState(() => new Date())
  return useMemo(() => {
    const { checks, doses } = sampleTrends(now, SAMPLE_DAYS)
    return { now, checks, doses, reference: firstWeek(checks), recent: lastDays(checks, now), sample: true }
  }, [now])
}
/** The same data limited to one hand's checks, with that hand's own first week and last 3 days. */
export function forHand(data: TrendsData, hand: HandFilter): TrendsData {
  if (hand === 'both') return data
  const checks = byHand(data.checks, hand)
  return { ...data, checks, reference: firstWeek(checks), recent: lastDays(checks, data.now) }
}
