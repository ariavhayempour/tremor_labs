import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { BLUE, NAVY } from './chartTheme'
import { ChartKey } from './ChartKey'
import { DayList } from './DayList'
import { fmtMeasure } from './format'
import { meanOf, usualRange, type TrendDay } from './model'
import { PeriodChart } from './PeriodChart'
import { StatLine } from './StatLine'
import type { Scales } from './scales'
import type { TrendsData } from './useTrendsData'
const t = copy.trends

/** The plain view: one chart per test, daily averages against the person's own usual range. */
export function OverviewSimple({ days, data, scale, onPick }: { days: TrendDay[]; data: TrendsData; scale: Scales; onPick: (date: string) => void }) {
  const restRange = usualRange(data.reference, 'rest'), total = days.reduce((a, d) => a + d.checks.length, 0)
  return <div className="trends-stack" role="tabpanel">
    <section className="home-card trends-card" aria-labelledby="trends-rest">
      <div className="trends-card-head"><div><h2 id="trends-rest">{t.restChart}</h2><p>{t.restChartBody} {total} {t.checks}.</p></div><ChartKey items={[['line', t.dailyAverage], ['band', t.usualRange]]}/></div>
      <PeriodChart days={days} height={320} y={scale.score} band={restRange} bandLabel label={t.restChart} onPick={onPick}
        series={[{ key: 'rest', color: BLUE }]} tipRows={[{ key: 'rest', label: t.measures.rest }]}/>
      <p className="trends-note"><Icon name="tap" size={17}/>{t.tapHint}</p>
    </section>
    <div className="trends-grid2">
      <section className="home-card trends-card" aria-labelledby="trends-posture">
        <div className="trends-card-head"><div><h2 id="trends-posture">{t.postureChart}</h2><p>{t.postureBody}</p></div></div>
        <StatLine k="posture" data={data}/>
        <PeriodChart days={days} y={scale.score} band={usualRange(data.reference, 'posture')} label={t.postureChart} onPick={onPick}
          series={[{ key: 'posture', color: BLUE }]} tipRows={[{ key: 'posture', label: t.measures.posture }]}/>
      </section>
      <section className="home-card trends-card" aria-labelledby="trends-reach">
        <div className="trends-card-head"><div><h2 id="trends-reach">{t.reachChart}</h2><p>{t.reachBody}</p></div></div>
        <StatLine k="reach" data={data}/>
        <PeriodChart days={days} y={scale.reach} ticks={4} band={usualRange(data.reference, 'reach')} label={t.reachChart} onPick={onPick}
          series={[{ key: 'reach', color: BLUE }]} tipRows={[{ key: 'reach', label: t.measures.reach }]}/>
      </section>
    </div>
    <section className="home-card trends-card" aria-labelledby="trends-tap">
      <div className="trends-card-head"><div><h2 id="trends-tap">{t.tapChart}</h2><p>{t.tapBody}</p></div><ChartKey items={[['line', t.left], ['dash', t.right]]}/></div>
      <p className="trends-stat">{t.last3} <strong>{fmtMeasure('tapL', meanOf(data.recent, 'tapL'))}</strong> <span>{t.tapStat} {t.leftShort.toLowerCase()} ·</span> <strong>{fmtMeasure('tapR', meanOf(data.recent, 'tapR'))}</strong> <span>{t.tapStat} {t.rightShort.toLowerCase()} · {t.tapFirstWeek} {fmtMeasure('tapL', meanOf(data.reference, 'tapL'))} {t.and} {fmtMeasure('tapR', meanOf(data.reference, 'tapR'))}</span></p>
      <PeriodChart days={days} y={scale.tap} label={t.tapChart} onPick={onPick}
        series={[{ key: 'tapL', color: BLUE, endLabel: t.leftShort }, { key: 'tapR', color: NAVY, dashed: true, hollow: true, endLabel: t.rightShort }]}
        tipRows={[{ key: 'tapL', label: t.left }, { key: 'tapR', label: t.right }]}/>
    </section>
    <section className="home-card trends-card" aria-labelledby="trends-days">
      <div className="trends-card-head"><div><h2 id="trends-days">{t.eachDay}</h2><p>{t.eachDayBody}{restRange ? ` (${restRange.n} ${t.checks}).` : '.'}</p></div></div>
      <DayList days={days} restRange={restRange} onPick={onPick}/>
    </section>
  </div>
}
