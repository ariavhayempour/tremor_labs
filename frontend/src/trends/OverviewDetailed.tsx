import { copy } from '../copy'
import { BLUE, NAVY } from './chartTheme'
import { ChartKey } from './ChartKey'
import { CheckDataTable } from './CheckDataTable'
import { DoseCurveChart } from './DoseCurveChart'
import { doseBins, usualRange, type MeasureKey, type TrendDay } from './model'
import { MeasureTable } from './MeasureTable'
import { PeriodChart } from './PeriodChart'
import type { Scales } from './scales'
import type { TrendsData } from './useTrendsData'
const t = copy.trends
const RAW_ROWS = 12

/** The full view: every check, every measure, dose timing, and the raw values. */
export function OverviewDetailed({ days, data, scale, onPick }: { days: TrendDay[]; data: TrendsData; scale: Scales; onPick: (date: string) => void }) {
  const checks = days.flatMap(d => d.checks)
  const { bins, returnsAfter } = doseBins(checks)
  const every = (k: MeasureKey, title: string, body: string, y: [number, number], yFormat?: (v: number) => string) =>
    <section className="home-card trends-card" aria-labelledby={`trends-${k}-every`}>
      <div className="trends-card-head"><div><h2 id={`trends-${k}-every`}>{title}</h2><p>{body}</p></div></div>
      <PeriodChart days={days} y={y} ticks={4} yFormat={yFormat} band={usualRange(data.reference, k)} label={title} onPick={onPick}
        series={[{ key: k, color: BLUE, every: true }, { key: k, color: BLUE, dots: false, width: 2 }]} tipRows={[{ key: k, label: t.measures[k] }]}/>
    </section>
  const hands = (kl: MeasureKey, kr: MeasureKey, title: string, body: string, y: [number, number]) =>
    <section className="home-card trends-card" aria-labelledby={`trends-${kl}`}>
      <div className="trends-card-head"><div><h2 id={`trends-${kl}`}>{title}</h2><p>{body}</p></div></div>
      <PeriodChart days={days} y={y} ticks={4} height={230} label={title} onPick={onPick}
        series={[{ key: kl, color: BLUE }, { key: kr, color: NAVY, dashed: true, hollow: true }]} tipRows={[{ key: kl, label: t.left }, { key: kr, label: t.right }]}/>
    </section>
  return <div className="trends-stack" role="tabpanel">
    <section className="home-card trends-card" aria-labelledby="trends-dose">
      <div className="trends-card-head"><div><h2 id="trends-dose">{t.doseChart}</h2><p>{t.doseBody}</p></div><ChartKey items={[['line', t.meanStrength], ['dose', t.risesAgain]]}/></div>
      <p className="trends-stat">{returnsAfter === null ? t.returnsUnknown : <>{t.returnsLead} <strong>{returnsAfter} h</strong> <span>{t.returnsTail}</span></>}</p>
      <DoseCurveChart bins={bins} returnsAfter={returnsAfter}/>
    </section>
    <div className="trends-grid2">
      {every('rest', t.restEvery, t.restEveryBody, scale.score)}
      {every('posture', t.postureEvery, t.postureEveryBody, scale.score)}
    </div>
    <section className="home-card trends-card" aria-labelledby="trends-rhythm">
      <div className="trends-card-head"><div><h2 id="trends-rhythm">{t.rhythmChart}</h2><p>{t.rhythmBody}</p></div><ChartKey items={[['dot', t.restShort], ['hollow', t.postureShort]]}/></div>
      <PeriodChart days={days} y={scale.hz} ticks={4} label={t.rhythmChart} onPick={onPick}
        series={[{ key: 'restHz', color: BLUE, every: true }, { key: 'postureHz', color: NAVY, every: true, hollow: true }]} tipRows={[{ key: 'restHz', label: t.restShort }, { key: 'postureHz', label: t.postureShort }]}/>
    </section>
    <div className="trends-grid2">
      {every('reach', t.reachEvery, t.reachEveryBody, scale.reach)}
      {every('endWobble', t.endWobbleChart, t.endWobbleBody, scale.endWobble, v => v.toFixed(1))}
    </div>
    <div>
      <div className="trends-grid3">
        {hands('tapL', 'tapR', t.tapSpeedChart, t.tapSpeedBody, scale.tap)}
        {hands('sizeL', 'sizeR', t.tapSizeChart, t.tapSizeBody, scale.size)}
        {hands('rhythmL', 'rhythmR', t.tapRhythmChart, t.tapRhythmBody, scale.rhythm)}
      </div>
      <ChartKey items={[['line', t.left], ['dash', t.right]]}/>
    </div>
    <section className="home-card trends-card" aria-labelledby="trends-profile">
      <div className="trends-card-head"><div><h2 id="trends-profile">{t.profileTitle}</h2><p>{t.profileBody}</p></div></div>
      <MeasureTable label={t.profileLabel} sets={[{ label: t.firstWeek, checks: data.reference }, { label: t.lastThree, checks: data.recent }]}/>
    </section>
    <section className="home-card trends-card" aria-labelledby="trends-all">
      <div className="trends-card-head"><div><h2 id="trends-all">{t.allChecks}</h2><p>{checks.length} {t.allChecksBody}</p></div></div>
      <CheckDataTable checks={[...checks].reverse()} doses={data.doses} onPick={onPick} limit={RAW_ROWS}/>
    </section>
  </div>
}
