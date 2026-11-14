import { lazy, Suspense } from 'react'
import type { HistoryEntry } from './homeStore'
const ActivityPlot = lazy(() => import('./ActivityPlot'))
export function ActivityChart({ history, days = 7 }: { history: HistoryEntry[]; days?: number }) {
  return <Suspense fallback={<div className="home-chart" aria-busy="true"/>}><ActivityPlot history={history} days={days}/></Suspense>
}
