import { useEffect, useState } from 'react'
import { getSummary, listChecks, USE_FIXTURES } from '../api/client'
import type { CheckOut, InsightsSummary } from '../api/types'
import { handSeries, windowStart, type HandPoint } from '../dashboard/format'
export interface HomeTrends { summary: InsightsSummary; latest: string | null; hands: HandPoint[] }
export type HomeTrendsState = { status: 'fixtures' } | { status: 'loading' } | { status: 'error' } | { status: 'ready'; data: HomeTrends }
const SUMMARY_DAYS = 14, HAND_DAYS = 7

/** Home's trend cards from the backend; fixture mode keeps the local sample data instead. */
export function useHomeTrends(): HomeTrendsState {
  const [state, setState] = useState<HomeTrendsState>(USE_FIXTURES ? { status: 'fixtures' } : { status: 'loading' })
  useEffect(() => {
    if (USE_FIXTURES) return
    let alive = true
    Promise.all([getSummary(SUMMARY_DAYS), listChecks({ from: windowStart(SUMMARY_DAYS).toISOString(), details: false })])
      .then(([summary, checks]: [InsightsSummary, CheckOut[]]) => {
        if (alive) setState({ status: 'ready', data: { summary, latest: checks[0]?.created_at ?? null, hands: handSeries(checks, HAND_DAYS) } })
      }, () => { if (alive) setState({ status: 'error' }) })
    return () => { alive = false }
  }, [])
  return state
}
