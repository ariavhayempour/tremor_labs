import { lazy, Suspense, useState } from 'react'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { dateLabel } from './homeStore'
import type { HandPoint } from '../dashboard/format'

const HandComparisonPlot = lazy(() => import('./HandComparisonPlot'))
function sampleComparison(): HandPoint[] {
  const left = [2.8, 3, 2.9, 3.1, 3, 3.2, 3.1]
  const right = [3.2, 3.3, 3.1, 3.4, 3.3, 3.5, 3.4]
  return left.map((value, index) => {
    const date = new Date()
    date.setDate(date.getDate() - (6 - index))
    return { day: dateLabel(date.toISOString()), left: value, right: right[index] }
  })
}
/** `live` is per-day tap rates from the backend; without it the card shows labeled sample data. */
export function HandComparison({ live }: { live?: HandPoint[] }) {
  const [sample] = useState(sampleComparison)
  const data = live ?? sample
  const values = (hand: 'left' | 'right') => data.map(point => point[hand]).filter((v): v is number => v !== null)
  const mean = (hand: 'left' | 'right') => { const v = values(hand); return v.length ? (v.reduce((a, b) => a + b, 0) / v.length).toFixed(2) : '—' }
  return <section className="home-card hand-comparison-card" aria-labelledby="hand-comparison-title">
    <div className="home-card-heading"><span className="home-card-icon"><Icon name="tap" size={21}/></span><div><h2 id="hand-comparison-title">{copy.home.handComparison}</h2><p>{copy.home.handSubtitle}</p></div>{!live && <span className="sample-badge">{copy.home.sampleComparison}</span>}</div>
    <div className="hand-comparison-metrics">{(['left', 'right'] as const).map(hand => <div key={hand} className={`hand-metric ${hand}`}><span className="hand-metric-label"><i/>{hand === 'left' ? copy.flow.leftHand : copy.flow.rightHand}</span><strong>{mean(hand)}<small>{copy.home.tapUnits}</small></strong><span className="hand-sample-count">{copy.home.average} · n={values(hand).length}</span></div>)}</div>
    <Suspense fallback={<div className="home-hand-chart" aria-busy="true"/>}><HandComparisonPlot data={data}/></Suspense>
    <div className="hand-comparison-footer"><span>{copy.home.handAxis}</span><span>{copy.home.last7DaysShort}</span></div>
  </section>
}
