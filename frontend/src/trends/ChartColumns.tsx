import type { ReactNode } from 'react'

export interface Column { a: number; b: number; tip: ReactNode; label: string; onPick?: () => void }
interface Props { columns: Column[]; domain: [number, number]; right: number; height: number; active: number | null; onActive: (index: number | null) => void }

/** Full-height buttons over a chart's plot area: large tap targets, keyboard focus, and a tooltip for the active column. */
export function ChartColumns({ columns, domain, right, height, active, onActive }: Props) {
  const span = domain[1] - domain[0]
  const at = (x: number) => `calc(var(--plot-left) + (100% - var(--plot-left) - ${right}px) * ${(x - domain[0]) / span})`
  const current = active === null ? null : columns[active]
  const flip = current ? (current.a + current.b) / 2 - domain[0] > span * 0.55 : false
  return <>
    {columns.map((col, i) => <button
      key={i} type="button" className="trends-hit" aria-label={col.label} tabIndex={col.onPick ? 0 : -1}
      style={{ left: at(col.a), width: `calc(${at(col.b)} - ${at(col.a)})`, height }}
      onPointerEnter={() => onActive(i)} onPointerLeave={() => onActive(null)} onFocus={() => onActive(i)} onBlur={() => onActive(null)}
      onClick={col.onPick} data-pickable={col.onPick ? '' : undefined}
    />)}
    {current && <div className="trends-tip" aria-hidden="true" style={flip ? { right: `calc(100% - ${at(current.a)} + 8px)` } : { left: `calc(${at(current.b)} + 8px)` }}>{current.tip}</div>}
  </>
}
