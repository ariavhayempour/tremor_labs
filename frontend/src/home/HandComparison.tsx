import { lazy, Suspense, useState } from 'react'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { dateLabel } from './homeStore'

const HandComparisonPlot = lazy(() => import('./HandComparisonPlot'))
export interface HandPoint { day: string; left: number; right: number }
function sampleComparison(): HandPoint[] {
  const left = [2.8, 3, 2.9, 3.1, 3, 3.2, 3.1]
  const right = [3.2, 3.3, 3.1, 3.4, 3.3, 3.5, 3.4]
  return left.map((value, index) => {
    const date = new Date()
    date.setDate(date.getDate() - (6 - index))
    return { day: dateLabel(date.toISOString()), left: value, right: right[index] }
  })
}
export function HandComparison() {
  const [data] = useState(sampleComparison)
  const mean = (hand: 'left' | 'right') => (data.reduce((sum, point) => sum + point[hand], 0) / data.length).toFixed(2)
  return <section className="home-card hand-comparison-card" aria-labelledby="hand-comparison-title">
    <div className="home-card-heading"><span className="home-card-icon"><Icon name="tap" size={21}/></span><div><h2 id="hand-comparison-title">{copy.home.handComparison}</h2><p>{copy.home.handSubtitle}</p></div><span className="sample-badge">{copy.home.sampleComparison}</span></div>
    <div className="hand-comparison-metrics">{(['left', 'right'] as const).map(hand => <div key={hand} className={`hand-metric ${hand}`}><span className="hand-metric-label"><i/>{hand === 'left' ? copy.flow.leftHand : copy.flow.rightHand}</span><strong>{mean(hand)}<small>{copy.home.tapUnits}</small></strong><span className="hand-sample-count">{copy.home.average} · n={data.length}</span></div>)}</div>
    <Suspense fallback={<div className="home-hand-chart" aria-busy="true"/>}><HandComparisonPlot data={data}/></Suspense>
    <div className="hand-comparison-footer"><span>{copy.home.handAxis}</span><span>{copy.home.last7DaysShort}</span></div>
  </section>
}
