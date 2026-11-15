import { useState, type ReactElement } from 'react'
import { CartesianGrid, ComposedChart, LabelList, Line, ReferenceArea, ReferenceLine, XAxis, YAxis } from 'recharts'
import type { CheckOut, DoseOut } from '../api/types'
import { copy } from '../copy'
import { ChartColumns, type Column } from './ChartColumns'
import { BAND_OPACITY, BASELINE, BLUE, DOSE, DOSE_INK, GRID, HIGHLIGHT, INK, MUTED, niceTicks, PLOT_LEFT, PLOT_RIGHT, prefersReducedMotion } from './chartTheme'
import { afterDose, clock, clockOfMinute, fmtMeasure, hourLabel, unitAfter } from './format'
import { doseSlot, MEASURES, minuteOfDay, type MeasureKey, type Range } from './model'
import { useWidth } from './useWidth'
const t = copy.trends

export interface DaySeries { key: MeasureKey; label: string; color: string; dashed?: boolean; hollow?: boolean; values?: boolean }
interface Props { checks: CheckOut[]; doses: DoseOut[]; allDoses: DoseOut[]; series: DaySeries[]; y: [number, number]; band?: Range | null; compact?: boolean; height?: number; label: string; onPick: (check: CheckOut) => void }
interface DotArgs { cx?: number; cy?: number; index?: number }
const START = 7 * 60, END = 22 * 60

/** One day on a clock axis, with logged doses marked; click a check to find it in the table. */
export function DayTimeChart({ checks, doses, allDoses, series, y, band, compact = false, height = 300, label, onPick }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const narrow = width < 560, animate = !prefersReducedMotion()
  const rows = checks.map((c, col) => ({ x: minuteOfDay(c.created_at), col, ...Object.fromEntries(series.map(s => [s.key, MEASURES[s.key].get(c)])) }))
  const hourTicks: number[] = []
  for (let h = 8; h <= 22; h += narrow || compact ? 4 : 2) hourTicks.push(h * 60)
  const mids = rows.map(r => r.x)
  const columns: Column[] = checks.map((c, i) => ({
    a: i ? (mids[i - 1] + mids[i]) / 2 : START, b: i < mids.length - 1 ? (mids[i] + mids[i + 1]) / 2 : END, onPick: () => onPick(c),
    label: `${clock(c.created_at)}: ${series.map(s => `${s.label} ${fmtMeasure(s.key, MEASURES[s.key].get(c))}`).join(', ')}. ${t.findCheckLabel}`,
    tip: <><b>{clock(c.created_at)}</b>{series.map(s => <div className="trends-tip-row" key={s.key}><span>{s.label}</span><strong>{fmtMeasure(s.key, MEASURES[s.key].get(c))}{unitAfter(s.key)}</strong></div>)}<div className="trends-tip-muted">{afterDose(c.minutes_since_dose, doseSlot(c, allDoses))}</div><div className="trends-tip-action">{t.findCheck}</div></>,
  }))
  const dot = (s: DaySeries) => ({ cx, cy, index }: DotArgs): ReactElement => cx === undefined || cy === undefined ? <g key={index}/> :
    <circle key={index} cx={cx} cy={cy} r={(compact ? 4.5 : 6) + (index === active ? 2 : 0)} fill={s.hollow ? '#fff' : s.color} stroke={s.hollow ? s.color : '#fff'} strokeWidth={2.5}/>
  return <div ref={ref} className="trends-chart" role="group" aria-label={label} style={{ height, ['--plot-left' as string]: `${PLOT_LEFT}px` }}>
    {width > 0 && <ComposedChart width={width} height={height} margin={{ top: 30, right: PLOT_RIGHT, bottom: 0, left: 0 }} data={rows}>
      <CartesianGrid vertical={false} stroke={GRID}/>
      {active !== null && <ReferenceArea x1={columns[active].a} x2={columns[active].b} y1={y[0]} y2={y[1]} fill={HIGHLIGHT} fillOpacity={1} ifOverflow="hidden"/>}
      {band && <ReferenceArea y1={band.lo} y2={band.hi} fill={BLUE} fillOpacity={BAND_OPACITY} ifOverflow="hidden"/>}
      {band && <ReferenceLine y={band.lo} stroke={BLUE} strokeOpacity={0.45} strokeDasharray="4 4"/>}
      {band && <ReferenceLine y={band.hi} stroke={BLUE} strokeOpacity={0.45} strokeDasharray="4 4"/>}
      {doses.map(d => { const m = minuteOfDay(d.taken_at); return <ReferenceLine key={d.id} x={m} stroke={DOSE} strokeWidth={1.5} strokeDasharray="3 4" ifOverflow="hidden"
        label={{ value: compact ? t.dose : `${t.dose} ${clockOfMinute(m)}`, position: 'top', fill: DOSE_INK, fontSize: 12, fontWeight: 600 }}/> })}
      <XAxis dataKey="x" type="number" domain={[START, END]} ticks={hourTicks} interval={0} allowDataOverflow axisLine={{ stroke: BASELINE }} tickLine={false} tick={{ fill: MUTED, fontSize: 12 }} tickFormatter={v => hourLabel(Number(v) / 60)}/>
      <YAxis type="number" domain={y} ticks={niceTicks(y[0], y[1], compact ? 4 : 5)} width={PLOT_LEFT} allowDataOverflow axisLine={false} tickLine={false} tick={{ fill: MUTED, fontSize: 12 }}/>
      {series.map(s => <Line key={s.key} dataKey={s.key} type="linear" stroke={s.color} strokeWidth={2.5} strokeDasharray={s.dashed ? '6 5' : undefined} dot={dot(s)} activeDot={false} connectNulls isAnimationActive={animate} animationDuration={700}>
        {s.values && <LabelList dataKey={s.key} position="top" offset={12} fill={INK} fontSize={compact ? 13 : 14} fontWeight={700} formatter={(v: unknown) => fmtMeasure(s.key, typeof v === 'number' ? v : null)}/>}
      </Line>)}
    </ComposedChart>}
    <ChartColumns columns={columns} domain={[START, END]} right={PLOT_RIGHT} height={height - 6} active={active} onActive={setActive}/>
  </div>
}
