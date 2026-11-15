import './trends.css'
import { useMemo } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import type { CheckOut } from '../api/types'
import { Icon } from '../components/Icon'
import { SegmentedControl } from '../components/SegmentedControl'
import { copy } from '../copy'
import { CompareHands } from './CompareHands'
import { DayDetailed } from './DayDetailed'
import { DayHeader } from './DayHeader'
import { DaySimple } from './DaySimple'
import { buildDays, meanOf, position, usualRange, type HandFilter } from './model'
import { OverviewDetailed } from './OverviewDetailed'
import { OverviewSimple } from './OverviewSimple'
import { scales } from './scales'
import { TrendsTabs, type TrendsView } from './TrendsTabs'
import { forHand, useTrendsData } from './useTrendsData'
const t = copy.trends
const PERIODS = [7, 14] as const
const DAY_VIEWS = ['simple', 'detailed'] as const
const FLASH_MS = 1400

/** Trends: plain, detailed and left/right views of the same checks, filterable by hand, with a per-day drill-down. */
export default function TrendsScreen() {
  const data = useTrendsData()
  const { date } = useParams()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const viewParam = params.get('view'), handParam = params.get('hand')
  const view: TrendsView = viewParam === 'detailed' || viewParam === 'compare' ? viewParam : 'simple'
  const hand: HandFilter = handParam === 'left' || handParam === 'right' ? handParam : 'both'
  const period = Number(params.get('days')) === 7 ? 7 : 14
  const shown = useMemo(() => forHand(data, hand), [data, hand])
  const allDays = useMemo(() => buildDays(shown.checks, 14, data.now), [shown, data.now])
  // One scale from every check, so switching hands never rescales a chart.
  const scale = useMemo(() => scales(data.checks), [data])
  const restRange = usualRange(shown.reference, 'rest')
  const query = (next: { view?: TrendsView; days?: number; hand?: HandFilter }) => {
    const p = new URLSearchParams()
    const v = next.view ?? view, h = next.hand ?? hand
    if (v !== 'simple') p.set('view', v)
    if ((next.days ?? period) === 7) p.set('days', '7')
    if (h !== 'both') p.set('hand', h)
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
  const handControl = <SegmentedControl<HandFilter> className="trends-hand" label={t.handFilter} value={hand} onChange={h => setParams(new URLSearchParams(query({ hand: h })), { replace: true })}
    options={[{ value: 'both', label: t.bothHands }, { value: 'left', label: t.left }, { value: 'right', label: t.right }]}/>
  const badge = data.sample && <span className="trends-sample" title={t.sampleNote}><Icon name="info" size={15}/>{t.sampleBadge}</span>

  if (date) {
    const i = allDays.findIndex(d => d.date === date)
    if (i < 0) return <div className="trends-page"><Link className="trends-back" to={`/dashboard${query({})}`}><Icon name="back" size={18}/>{t.back}</Link><p className="trends-summary">{t.dayNotFound}</p></div>
    const day = allDays[i], dayView = view === 'detailed' ? 'detailed' : 'simple'
    return <div className="trends-page">
      <DayHeader day={day} prev={allDays[i - 1]} next={allDays[i + 1]} doses={data.doses} restRange={restRange} onBack={() => navigate(`/dashboard${query({})}`)} onStep={openDay}/>
      <div className="trends-controls"><TrendsTabs view={dayView} views={DAY_VIEWS} onChange={setView}/><div className="trends-filters">{handControl}{badge}</div></div>
      {dayView === 'detailed' ? <DayDetailed day={day} data={shown} hand={hand} scale={scale} onFind={findCheck}/> : <DaySimple day={day} data={shown} scale={scale} onFind={findCheck}/>}
    </div>
  }

  const days = allDays.slice(-period)
  const recentRest = meanOf(shown.recent, 'rest'), where = position(recentRest, restRange)
  return <div className="trends-page">
    <div className="trends-title"><h1>{t.title}</h1>{badge}</div>
    {view === 'compare' ? <p className="trends-summary">{t.compareIntro}</p>
      : view === 'detailed' ? <p className="trends-summary">{t.detailedIntro}</p>
      : <p className="trends-summary">{recentRest === null ? t.summaryNoData : <>{t.summaryLead} <strong>{Math.round(recentRest)}</strong>{where && restRange ? <>, <strong>{t[where]}</strong> <span className="nowrap">({Math.round(restRange.lo)} {t.to} {Math.round(restRange.hi)}).</span></> : <>. {t.building}</>}</>}</p>}
    <div className="trends-controls"><TrendsTabs view={view} onChange={setView}/>
      <div className="trends-filters">{view !== 'compare' && handControl}
        <SegmentedControl<number> className="history-period" label={t.period} value={period} onChange={d => setParams(new URLSearchParams(query({ days: d })), { replace: true })}
          options={[{ value: PERIODS[0], label: t.last7 }, { value: PERIODS[1], label: t.last14 }]}/>
      </div>
    </div>
    {view === 'compare' ? <CompareHands days={buildDays(data.checks, period, data.now)} scale={scale} onPick={openDay}/>
      : view === 'detailed' ? <OverviewDetailed days={days} data={shown} hand={hand} scale={scale} onPick={openDay}/>
      : <OverviewSimple days={days} data={shown} hand={hand} scale={scale} onPick={openDay}/>}
  </div>
}
