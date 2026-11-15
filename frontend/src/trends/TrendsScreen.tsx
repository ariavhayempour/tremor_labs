import './trends.css'
import { useMemo } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import type { CheckOut } from '../api/types'
import { Icon } from '../components/Icon'
import { SegmentedControl } from '../components/SegmentedControl'
import { copy } from '../copy'
import { DayDetailed } from './DayDetailed'
import { DayHeader } from './DayHeader'
import { DaySimple } from './DaySimple'
import { buildDays, meanOf, position, usualRange } from './model'
import { OverviewDetailed } from './OverviewDetailed'
import { OverviewSimple } from './OverviewSimple'
import { scales } from './scales'
import { TrendsTabs, type TrendsView } from './TrendsTabs'
import { useTrendsData } from './useTrendsData'
const t = copy.trends
const PERIODS = [7, 14] as const
const FLASH_MS = 1400

/** Trends: a plain overview and a detailed view of the same checks, each with a per-day drill-down. */
export default function TrendsScreen() {
  const data = useTrendsData()
  const { date } = useParams()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const view: TrendsView = params.get('view') === 'detailed' ? 'detailed' : 'simple'
  const period = Number(params.get('days')) === 7 ? 7 : 14
  const allDays = useMemo(() => buildDays(data.checks, 14, data.now), [data])
  const scale = useMemo(() => scales(data.checks), [data])
  const restRange = usualRange(data.reference, 'rest')
  const query = (next: { view?: TrendsView; days?: number }) => {
    const p = new URLSearchParams()
    if ((next.view ?? view) === 'detailed') p.set('view', 'detailed')
    if ((next.days ?? period) === 7) p.set('days', '7')
    const s = p.toString()
    return s ? `?${s}` : ''
  }
  const openDay = (d: string) => navigate(`/dashboard/day/${d}${query({})}`)
  const findCheck = (c: CheckOut) => {
    const row = document.getElementById(`check-${c.id}`)
    if (!row) return
    row.scrollIntoView({ behavior: 'smooth', block: 'center' })
    row.classList.add('flash'); window.setTimeout(() => row.classList.remove('flash'), FLASH_MS)
  }
  const setView = (v: TrendsView) => setParams(new URLSearchParams(query({ view: v })), { replace: true })
  const tabs = <TrendsTabs view={view} onChange={setView}/>
  const badge = data.sample && <span className="trends-sample" title={t.sampleNote}><Icon name="info" size={15}/>{t.sampleBadge}</span>

  if (date) {
    const i = allDays.findIndex(d => d.date === date)
    if (i < 0) return <div className="trends-page"><Link className="trends-back" to={`/dashboard${query({})}`}><Icon name="back" size={18}/>{t.back}</Link><p className="trends-summary">{t.dayNotFound}</p></div>
    const day = allDays[i]
    return <div className="trends-page">
      <DayHeader day={day} prev={allDays[i - 1]} next={allDays[i + 1]} doses={data.doses} restRange={restRange} onBack={() => navigate(`/dashboard${query({})}`)} onStep={openDay}/>
      <div className="trends-controls">{tabs}{badge}</div>
      {view === 'detailed' ? <DayDetailed day={day} data={data} scale={scale} onFind={findCheck}/> : <DaySimple day={day} data={data} scale={scale} onFind={findCheck}/>}
    </div>
  }

  const days = allDays.slice(-period)
  const recentRest = meanOf(data.recent, 'rest'), where = position(recentRest, restRange)
  return <div className="trends-page">
    <div className="trends-title"><h1>{t.title}</h1>{badge}</div>
    {view === 'detailed' ? <p className="trends-summary">{t.detailedIntro}</p>
      : <p className="trends-summary">{recentRest === null ? t.summaryNoData : <>{t.summaryLead} <strong>{Math.round(recentRest)}</strong>{where && restRange ? <>, <strong>{t[where]}</strong> <span className="nowrap">({Math.round(restRange.lo)} {t.to} {Math.round(restRange.hi)}).</span></> : <>. {t.building}</>}</>}</p>}
    <div className="trends-controls">{tabs}
      <SegmentedControl<number> className="history-period" label={t.period} value={period} onChange={d => setParams(new URLSearchParams(query({ days: d })), { replace: true })}
        options={[{ value: PERIODS[0], label: t.last7 }, { value: PERIODS[1], label: t.last14 }]}/>
    </div>
    {view === 'detailed' ? <OverviewDetailed days={days} data={data} scale={scale} onPick={openDay}/> : <OverviewSimple days={days} data={data} scale={scale} onPick={openDay}/>}
  </div>
}
