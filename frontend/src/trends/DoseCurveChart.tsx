import { useState } from 'react'
import { CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, XAxis, YAxis } from 'recharts'
import type { Bin } from '../api/types'
import { copy } from '../copy'
import { ChartColumns, type Column } from './ChartColumns'
import { BASELINE, BLUE, DOSE, DOSE_INK, GRID, HIGHLIGHT, INK, MUTED, niceMax, niceTicks, PLOT_LEFT, PLOT_RIGHT, prefersReducedMotion } from './chartTheme'
import { useWidth } from './useWidth'
const t = copy.trends
const HOURS = [0, 1, 2, 3, 4, 5, 6]

/** Mean rest strength by hours since a dose, with the check count under each half-hour bin. */
export function DoseCurveChart({ bins, returnsAfter, height = 320 }: { bins: Bin[]; returnsAfter: number | null; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const rows = bins.map((b, col) => ({ x: b.start_h + 0.25, mean: b.mean, count: b.count, col }))
  const top = niceMax(Math.max(0.1, ...bins.map(b => b.mean)) * 1.15, 0.1)
  const columns: Column[] = bins.map(b => ({
    a: b.start_h, b: b.start_h + 0.5,
    label: `${b.start_h}–${b.start_h + 0.5} ${t.hoursAfter}: ${b.mean.toFixed(3)} m/s², ${b.count} ${t.checks}`,
    tip: <><b>{b.start_h}–{b.start_h + 0.5} {t.hoursAfter}</b><div className="trends-tip-row"><span>{t.meanStrength}</span><strong>{b.mean.toFixed(3)}</strong></div><div className="trends-tip-muted">{b.count} {t.checks}{b.count < 3 ? ` · ${t.fewChecks}` : ''}</div></>,
  }))
  const summary = returnsAfter === null ? t.returnsUnknown : `${t.returnsLead} ${returnsAfter} h ${t.returnsTail}`
  return <div ref={ref} className="trends-chart" role="group" aria-label={`${t.doseChart}. ${summary}`} style={{ height, ['--plot-left' as string]: `${PLOT_LEFT}px` }}>
    {width > 0 && <ComposedChart width={width} height={height} margin={{ top: 30, right: PLOT_RIGHT, bottom: 0, left: 0 }} data={rows}>
      <CartesianGrid vertical={false} stroke={GRID}/>
      {active !== null && <ReferenceArea x1={columns[active].a} x2={columns[active].b} y1={0} y2={top} fill={HIGHLIGHT} fillOpacity={1} ifOverflow="hidden"/>}
      {returnsAfter !== null && <ReferenceLine x={returnsAfter} stroke={DOSE} strokeWidth={1.5} strokeDasharray="3 4" label={{ value: `${t.risesAgain} ≈ ${returnsAfter} h`, position: 'top', fill: DOSE_INK, fontSize: 12, fontWeight: 600 }}/>}
      <XAxis dataKey="x" type="number" domain={[0, 6]} ticks={HOURS} interval={0} axisLine={{ stroke: BASELINE }} tickLine={false} tick={{ fill: INK, fontSize: 12.5 }} tickFormatter={v => Number(v) ? `${v} h` : t.doseTick}/>
      <XAxis xAxisId="n" dataKey="x" type="number" domain={[0, 6]} ticks={rows.map(r => r.x)} interval={0} axisLine={false} tickLine={false} height={20} tick={{ fill: MUTED, fontSize: 12 }} tickFormatter={v => String(rows.find(r => r.x === Number(v))?.count ?? '')}/>
      <YAxis type="number" domain={[0, top]} ticks={niceTicks(0, top, 4)} width={PLOT_LEFT} axisLine={false} tickLine={false} tick={{ fill: MUTED, fontSize: 12 }} tickFormatter={v => Number(v).toFixed(2)}/>
      <Line dataKey="mean" type="linear" stroke={BLUE} strokeWidth={2.5} dot={{ r: 4.5, fill: BLUE, stroke: '#fff', strokeWidth: 2 }} activeDot={false} isAnimationActive={!prefersReducedMotion()} animationDuration={900}/>
    </ComposedChart>}
    <span className="trends-n" aria-hidden="true">n</span>
    <ChartColumns columns={columns} domain={[0, 6]} right={PLOT_RIGHT} height={height - 6} active={active} onActive={setActive}/>
  </div>
}
