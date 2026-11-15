import type { CheckOut } from '../api/types'
import { copy } from '../copy'
import { BLUE, NAVY } from './chartTheme'
import { ChartKey } from './ChartKey'
import { CheckDataTable } from './CheckDataTable'
import { DayTimeChart, type DaySeries } from './DayTimeChart'
import { dosesOn, usualRange, type MeasureKey, type TrendDay } from './model'
import { MeasureTable } from './MeasureTable'
import type { Scales } from './scales'
import type { TrendsData } from './useTrendsData'
const t = copy.trends

/** One day in full: every measure on a clock axis, the day against the first week, and the raw values. */
export function DayDetailed({ day, data, scale, onFind }: { day: TrendDay; data: TrendsData; scale: Scales; onFind: (check: CheckOut) => void }) {
  const doses = dosesOn(data.doses, day.date)
  const chart = (id: string, title: string, body: string, y: [number, number], series: DaySeries[], band: MeasureKey | null, key?: boolean) =>
    <section className="home-card trends-card" aria-labelledby={id}>
      <div className="trends-card-head"><div><h2 id={id}>{title}</h2><p>{body}</p></div>{key && <ChartKey items={[['line', t.leftShort], ['dash', t.rightShort]]}/>}</div>
      <DayTimeChart compact height={240} checks={day.checks} doses={doses} allDoses={data.doses} y={y} band={band ? usualRange(data.reference, band) : null} label={title} onPick={onFind} series={series}/>
    </section>
  return <div className="trends-stack" role="tabpanel">
    <p className="trends-section-note">{t.everyMeasure}</p>
    <div className="trends-grid2">
      {chart('day-rest', t.measures.rest, `${t.cols.score} 0–100`, scale.score, [{ key: 'rest', label: t.restShort, color: BLUE, values: true }], 'rest')}
      {chart('day-posture', t.measures.posture, `${t.cols.score} 0–100`, scale.score, [{ key: 'posture', label: t.postureShort, color: BLUE, values: true }], 'posture')}
      {chart('day-reach', t.measures.reach, t.reachEveryBody, scale.reach, [{ key: 'reach', label: t.reachCol, color: BLUE, values: true }], 'reach')}
      {chart('day-tap', t.measures.tap, t.tapSpeedBody, scale.tap, [{ key: 'tapL', label: t.leftShort, color: BLUE }, { key: 'tapR', label: t.rightShort, color: NAVY, dashed: true, hollow: true }], null, true)}
    </div>
    <section className="home-card trends-card" aria-labelledby="day-profile">
      <div className="trends-card-head"><div><h2 id="day-profile">{t.dayCompare}</h2><p>{t.dayProfile}</p></div></div>
      <MeasureTable label={t.profileLabel} sets={[{ label: t.firstWeek, checks: data.reference }, { label: t.thisDay, checks: day.checks }]}/>
    </section>
    <section className="home-card trends-card" aria-labelledby="day-data">
      <div className="trends-card-head"><div><h2 id="day-data">{t.dayData}</h2><p>{t.dayDataBody}</p></div></div>
      <CheckDataTable checks={day.checks} doses={data.doses}/>
    </section>
  </div>
}
