import { useMemo, useState } from 'react'
import type { CheckOut, DoseOut } from '../api/types'
import { readPreferences } from '../home/homeStore'
import { firstWeek, lastDays } from './model'
import { sampleTrends } from './sampleTrends'

export interface TrendsData { now: Date; checks: CheckOut[]; doses: DoseOut[]; reference: CheckOut[]; recent: CheckOut[]; sample: boolean }
const SAMPLE_DAYS = 14

/** The trends screen's data. Sample checks for now; they use the same shapes as `GET /api/checks` and `GET /api/doses`. */
export function useTrendsData(): TrendsData {
  const [now] = useState(() => new Date())
  return useMemo(() => {
    const { checks, doses } = sampleTrends(now, SAMPLE_DAYS, readPreferences().hand === 'left' ? 'left' : 'right')
    return { now, checks, doses, reference: firstWeek(checks), recent: lastDays(checks, now), sample: true }
  }, [now])
}
