import type { CheckOut } from '../api/types'
import { copy } from '../copy'
import { BLUE } from './chartTheme'
import { ChartKey } from './ChartKey'
import { CompareStrip } from './CompareStrip'
import { DayCheckList } from './DayCheckList'
import { DayTimeChart } from './DayTimeChart'
import { dosesOn, usualRange, type TrendDay } from './model'
import type { Scales } from './scales'
import type { TrendsData } from './useTrendsData'
const t = copy.trends

/** One day in plain terms: rest tremor around doses, the day against the first week, and each check. */
export function DaySimple({ day, data, scale, onFind }: { day: TrendDay; data: TrendsData; scale: Scales; onFind: (check: CheckOut) => void }) {
  return <div className="trends-stack" role="tabpanel">
    <section className="home-card trends-card" aria-labelledby="day-through">
      <div className="trends-card-head"><div><h2 id="day-through">{t.throughDay}</h2><p>{t.throughDayBody}</p></div><ChartKey items={[['line', t.restCol], ['dose', t.dose], ['band', t.usualRange]]}/></div>
      <DayTimeChart checks={day.checks} doses={dosesOn(data.doses, day.date)} allDoses={data.doses} y={scale.score} band={usualRange(data.reference, 'rest')} label={t.throughDay} onPick={onFind}
        series={[{ key: 'rest', label: t.restCol, color: BLUE, values: true }]}/>
    </section>
    <section className="home-card trends-card" aria-labelledby="day-compare">
      <div className="trends-card-head"><div><h2 id="day-compare">{t.dayCompare}</h2><p>{t.dayCompareBody}, n={data.reference.length} {t.checks}.</p></div></div>
      <CompareStrip checks={day.checks} reference={data.reference}/>
    </section>
    <section className="home-card trends-card" aria-labelledby="day-checks">
      <div className="trends-card-head"><div><h2 id="day-checks">{t.everyCheck}</h2><p>{t.everyCheckBody}</p></div></div>
      <DayCheckList checks={day.checks} doses={data.doses} linkResults={!data.sample}/>
      <p className="trends-footnote">{t.footNote}</p>
    </section>
  </div>
}
