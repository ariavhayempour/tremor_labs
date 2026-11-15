import { useEffect, useState } from 'react'
import { getDoseResponse, getProfile, getSummary, listChecks } from '../api/client'
import type { CheckOut, DoseResponseOut, InsightsSummary, ProfileRow } from '../api/types'
import { windowStart } from './format'
export interface DashboardData { summary: InsightsSummary; dose: DoseResponseOut; profile: ProfileRow[]; checks: CheckOut[] }
export type DashboardState = { status: 'loading' } | { status: 'error' } | { status: 'ready'; data: DashboardData }

/** Every dashboard insight for the last `days` local calendar days, loaded together. */
export function useDashboard(days: number): DashboardState {
  const [state, setState] = useState<{ days: number; value: DashboardState } | null>(null)
  useEffect(() => {
    let alive = true
    Promise.all([getSummary(days), getDoseResponse(days), getProfile(days), listChecks({ from: windowStart(days).toISOString(), details: false })])
      .then(([summary, dose, profile, checks]) => { if (alive) setState({ days, value: { status: 'ready', data: { summary, dose, profile, checks } } }) },
        () => { if (alive) setState({ days, value: { status: 'error' } }) })
    return () => { alive = false }
  }, [days])
  return state && state.days === days ? state.value : { status: 'loading' }
}
