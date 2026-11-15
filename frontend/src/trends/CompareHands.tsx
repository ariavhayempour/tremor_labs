import type { CheckOut } from '../api/types'
import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { BLUE, NAVY } from './chartTheme'
import { ChartKey } from './ChartKey'
import { fmtMeasure, unitOf } from './format'
import { MeasureTable } from './MeasureTable'
import { byHand, compare, meanOf, ONE_HAND_MEASURES, type MeasureKey, type TrendDay } from './model'
import { PeriodChart } from './PeriodChart'
import type { Scales } from './scales'
const t = copy.trends
const HEADLINE: MeasureKey[] = ['rest', 'posture', 'reach', 'tap']

/** Left-hand checks beside right-hand checks over the chosen period: headline averages, daily charts and every measure. */
export function CompareHands({ days, scale, onPick }: { days: TrendDay[]; scale: Scales; onPick: (date: string) => void }) {
  const checks = days.flatMap(d => d.checks)
  const left = byHand(checks, 'left'), right = byHand(checks, 'right')
  const chart = (k: MeasureKey, title: string, body: string, y: [number, number]) =>
    <section className="home-card trends-card" aria-labelledby={`compare-${k}`}>
      <div className="trends-card-head"><div><h2 id={`compare-${k}`}>{title}</h2><p>{body}</p></div></div>
      <PeriodChart days={days} y={y} ticks={4} label={title} onPick={onPick}
        series={[{ key: k, hand: 'left', color: BLUE, endLabel: t.leftShort }, { key: k, hand: 'right', color: NAVY, dashed: true, hollow: true, endLabel: t.rightShort }]}
        tipRows={[{ key: k, hand: 'left', label: t.left }, { key: k, hand: 'right', label: t.right }]}/>
    </section>
  return <div className="trends-stack" role="tabpanel">
    <section className="home-card trends-card" aria-labelledby="compare-summary">
      <div className="trends-card-head"><div><h2 id="compare-summary">{t.compareTitle}</h2><p>{t.compareBody} {t.left} n={left.length}, {t.right.toLowerCase()} n={right.length} {t.checks}.</p></div></div>
      <HandStrip left={left} right={right}/>
    </section>
    <div>
      <div className="trends-grid2">
        {chart('rest', t.restChart, t.restChartBody, scale.score)}
        {chart('posture', t.postureChart, t.postureBody, scale.score)}
        {chart('reach', t.reachChart, t.reachBody, scale.reach)}
        {chart('tap', t.tapSpeedChart, t.tapBody, scale.tap)}
      </div>
      <ChartKey items={[['line', t.left], ['dash', t.right]]}/>
    </div>
    <section className="home-card trends-card" aria-labelledby="compare-all">
      <div className="trends-card-head"><div><h2 id="compare-all">{t.compareTable}</h2><p>{t.compareTableBody}</p></div></div>
      <MeasureTable label={t.compareTable} keys={ONE_HAND_MEASURES} changeLabel={t.rightVsLeft} sets={[{ label: t.left, checks: left }, { label: t.right, checks: right }]}/>
    </section>
  </div>
}

/** The four headline tests, left and right averages side by side, with the right hand described against the left. */
function HandStrip({ left, right }: { left: CheckOut[]; right: CheckOut[] }) {
  return <div className="trends-compare">{HEADLINE.map(k => {
    const l = meanOf(left, k), r = meanOf(right, k), change = compare(r, l)
    return <div key={k}>
      <h3>{t.measures[k]}</h3>
      <dl className="trends-hands">
        <div><dt>{t.leftShort}</dt><dd>{fmtMeasure(k, l)}</dd></div>
        <div><dt>{t.rightShort}</dt><dd>{fmtMeasure(k, r)}</dd></div>
      </dl>
      <p className="ref">{unitOf(k)}</p>
      {change && <span className="trends-pill"><Icon name={change === 'same' ? 'same' : change === 'higher' ? 'up' : 'down'} size={15}/>{t.handChange[change]}</span>}
    </div>
  })}</div>
}
