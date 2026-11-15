import { useState, type ReactElement } from 'react'
import type { CheckOut, Hand } from '../api/types'
import { CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, XAxis, YAxis } from 'recharts'
import { copy } from '../copy'
import { ChartColumns, type Column } from './ChartColumns'
import { BAND_OPACITY, BASELINE, BLUE, END_LABEL_RIGHT, GRID, HIGHLIGHT, INK, MUTED, niceTicks, PLOT_LEFT, PLOT_RIGHT, prefersReducedMotion } from './chartTheme'
import { dayOfMonth, fmtMeasure, longDate, shortDate, unitAfter } from './format'
import { byHand, MEASURES, mean, minuteOfDay, type MeasureKey, type Range, type TrendDay } from './model'
import { useWidth } from './useWidth'
const t = copy.trends

/** With `hand`, a series or tooltip row uses only that hand's checks. */
export interface PeriodSeries { key: MeasureKey; hand?: Hand; color: string; dashed?: boolean; hollow?: boolean; every?: boolean; dots?: boolean; width?: number; endLabel?: string }
export interface TipRow { key: MeasureKey; hand?: Hand; label: string }
interface Props {
  days: TrendDay[]; series: PeriodSeries[]; tipRows: TipRow[]; y: [number, number]
  ticks?: number; yFormat?: (v: number) => string; band?: Range | null; bandLabel?: boolean; height?: number; label: string; onPick: (date: string) => void
}
interface Point { x: number; y: number | null; col: number }
interface DotArgs { cx?: number; cy?: number; index?: number; payload?: Point }
interface LabelArgs { x?: number | string; y?: number | string; index?: number }
const AXIS_HEIGHT = 46
// Places a check inside its day's column by time of day, 7 AM to 10 PM.
const inColumn = (col: number, iso: string) => col + 0.14 + 0.72 * Math.min(1, Math.max(0, (minuteOfDay(iso) - 420) / 900))
const dayMean = (checks: CheckOut[], r: { key: MeasureKey; hand?: Hand }) => mean(byHand(checks, r.hand ?? 'both').map(MEASURES[r.key].get))

/** A chart across days: one column per day, click a column to open that day. */
export function PeriodChart({ days, series, tipRows, y, ticks = 5, yFormat, band, bandLabel = false, height = 270, label, onPick }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const narrow = width < 560, n = days.length, animate = !prefersReducedMotion()
  const right = series.some(s => s.endLabel) ? END_LABEL_RIGHT : PLOT_RIGHT
  const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((width - 70) / (narrow ? 34 : 64)))))
  const tickValues = days.map((_, i) => i).filter(i => (n - 1 - i) % every === 0).map(i => i + 0.5)
  const firstTick = tickValues[0]
  const points = (s: PeriodSeries): Point[] => s.every
    ? days.flatMap((d, col) => byHand(d.checks, s.hand ?? 'both').map(c => ({ x: inColumn(col, c.created_at), y: MEASURES[s.key].get(c), col })))
    : days.map((d, col) => ({ x: col + 0.5, y: dayMean(d.checks, s), col }))
  const columns: Column[] = days.map((d, i) => ({
    a: i, b: i + 1, onPick: () => onPick(d.date),
    label: `${longDate(d.date)}: ${tipRows.map(r => `${r.label} ${fmtMeasure(r.key, dayMean(d.checks, r))}`).join(', ')}, ${d.checks.length} ${t.checks}. ${t.openDayLabel}`,
    tip: <><b>{longDate(d.date)}</b>{tipRows.map(r => <div className="trends-tip-row" key={`${r.key}-${r.hand ?? 'both'}`}><span>{r.label}</span><strong>{fmtMeasure(r.key, dayMean(d.checks, r))}{unitAfter(r.key)}</strong></div>)}<div className="trends-tip-muted">{d.checks.length ? `${d.checks.length} ${t.checks}` : t.noChecks}</div><div className="trends-tip-action">{t.openDay}</div></>,
  }))
  const dot = (s: PeriodSeries) => ({ cx, cy, index, payload }: DotArgs): ReactElement => {
    if (cx === undefined || cy === undefined || payload?.y === null) return <g key={index}/>
    const r = (s.every ? 3.5 : 4.5) + (payload?.col === active ? 2.5 : 0)
    return <circle key={index} cx={cx} cy={cy} r={r} fill={s.hollow ? '#fff' : s.color} stroke={s.hollow ? s.color : '#fff'} strokeWidth={2} fillOpacity={s.every && !s.hollow ? 0.6 : 1}/>
  }
  const endLabel = (s: PeriodSeries, last: number) => ({ x, y: ly, index }: LabelArgs): ReactElement =>
    index === last ? <text key="end" x={Number(x) + 10} y={Number(ly) + (s.dashed ? -6 : 14)} fill={INK} fontSize={12.5} fontWeight={600}>{s.endLabel}</text> : <g key={index}/>
  const DayTick = ({ x, y: ty, payload }: { x?: number | string; y?: number | string; payload?: { value?: unknown } }) => {
    const value = Number(payload?.value ?? 0), d = days[Math.floor(value)]
    if (!d) return <g/>
    return <g transform={`translate(${Number(x ?? 0)},${Number(ty ?? 0)})`}><text dy={12} textAnchor="middle" fill={INK} fontSize={12.5}>{narrow && value !== firstTick ? dayOfMonth(d.date) : shortDate(d.date)}</text><text dy={31} textAnchor="middle" fill={MUTED} fontSize={12}>{d.checks.length}</text></g>
  }
  return <div ref={ref} className="trends-chart" role="group" aria-label={label} style={{ height, ['--plot-left' as string]: `${PLOT_LEFT}px` }}>
    {width > 0 && <ComposedChart width={width} height={height} margin={{ top: 14, right, bottom: 0, left: 0 }} data={[]}>
      <CartesianGrid vertical={false} stroke={GRID}/>
      {active !== null && <ReferenceArea x1={active} x2={active + 1} y1={y[0]} y2={y[1]} fill={HIGHLIGHT} fillOpacity={1} ifOverflow="hidden"/>}
      {band && <ReferenceArea y1={band.lo} y2={band.hi} fill={BLUE} fillOpacity={BAND_OPACITY} ifOverflow="hidden"/>}
      {band && <ReferenceLine y={band.lo} stroke={BLUE} strokeOpacity={0.45} strokeDasharray="4 4"/>}
      {band && <ReferenceLine y={band.hi} stroke={BLUE} strokeOpacity={0.45} strokeDasharray="4 4" label={bandLabel ? { value: t.usualRange, position: 'insideTopLeft', fill: MUTED, fontSize: 12, dy: -18 } : undefined}/>}
      <XAxis dataKey="x" type="number" domain={[0, n]} ticks={tickValues} interval={0} allowDataOverflow axisLine={{ stroke: BASELINE }} tickLine={false} height={AXIS_HEIGHT} tick={DayTick}/>
      <YAxis dataKey="y" type="number" domain={y} ticks={niceTicks(y[0], y[1], ticks)} width={PLOT_LEFT} allowDataOverflow axisLine={false} tickLine={false} tick={{ fill: MUTED, fontSize: 12 }} tickFormatter={yFormat}/>
      {series.map(s => { const pts = points(s); const last = pts.findLastIndex(p => p.y !== null); return <Line
        key={`${s.key}-${s.hand ?? 'both'}-${s.every ? 'every' : 'mean'}`} data={pts} dataKey="y" type="linear" stroke={s.every ? 'none' : s.color} strokeWidth={s.width ?? 2.5}
        strokeDasharray={s.dashed ? '6 5' : undefined} dot={s.dots === false ? false : dot(s)} activeDot={false} connectNulls={false}
        isAnimationActive={animate && !s.every} animationDuration={900} label={s.endLabel ? endLabel(s, last) : undefined}
      /> })}
    </ComposedChart>}
    <span className="trends-n" aria-hidden="true">n</span>
    <ChartColumns columns={columns} domain={[0, n]} right={right} height={height - 6} active={active} onActive={setActive}/>
  </div>
}
