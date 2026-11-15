import { lazy, Suspense } from 'react'
import type { HistoryEntry } from './homeStore'
const ActivityPlot = lazy(() => import('./ActivityPlot'))
export function ActivityChart({ history = [], days = 7, data }: { history?: HistoryEntry[]; days?: number; data?: { day: string; count: number }[] }) {
  return <Suspense fallback={<div className="home-chart" aria-busy="true"/>}><ActivityPlot history={history} days={days} data={data}/></Suspense>
}
