import { useState } from 'react'
import type { CheckOut, DoseOut } from '../api/types'
import { copy } from '../copy'
import { afterDose, clock, fmtMeasure, shortDate, weekday } from './format'
import { checkDate, doseSlot, MEASURES, type MeasureKey } from './model'
const t = copy.trends
const c = t.cols, u = t.units
const COLUMNS: { key: MeasureKey; head: string; unit: string; sep?: boolean }[] = [
  { key: 'rest', head: c.score, unit: u.score, sep: true }, { key: 'restStrength', head: c.strength, unit: u.ms2 }, { key: 'restHz', head: c.rhythm, unit: u.hz },
  { key: 'posture', head: c.score, unit: u.score, sep: true }, { key: 'postureHz', head: c.rhythm, unit: u.hz }, { key: 'held', head: c.held, unit: u.s },
  { key: 'reach', head: c.wobble, unit: u.mm, sep: true }, { key: 'endWobble', head: c.endWobble, unit: u.ratio },
  { key: 'tapL', head: c.speedL, unit: u.taps, sep: true }, { key: 'tapR', head: c.speedR, unit: u.taps }, { key: 'sizeL', head: c.sizeL, unit: u.pct }, { key: 'sizeR', head: c.sizeR, unit: u.pct },
  { key: 'rhythmL', head: c.rhythmL, unit: c.variation }, { key: 'rhythmR', head: c.rhythmR, unit: c.variation },
]

/** Every recorded value per check. With `onPick`, rows open their day; `limit` collapses long lists behind a button. */
export function CheckDataTable({ checks, doses, onPick, limit = Infinity }: { checks: CheckOut[]; doses: DoseOut[]; onPick?: (date: string) => void; limit?: number }) {
  const [all, setAll] = useState(false)
  const shown = all ? checks : checks.slice(0, limit)
  return <>
    <div className="trends-scroll" tabIndex={0} role="region" aria-label={t.allChecksLabel}><table className="trends-data">
      <thead>
        <tr className="group"><td/><th scope="colgroup" colSpan={3} className="sep">{t.groups.rest}</th><th scope="colgroup" colSpan={3} className="sep">{t.groups.posture}</th><th scope="colgroup" colSpan={2} className="sep">{t.groups.reach}</th><th scope="colgroup" colSpan={6} className="sep">{t.groups.tap}</th></tr>
        <tr><th scope="col">{t.time}</th>{COLUMNS.map(col => <th scope="col" key={col.key} className={col.sep ? 'sep' : undefined}>{col.head}<small>{col.unit}</small></th>)}</tr>
      </thead>
      <tbody>{shown.map(check => { const when = afterDose(check.minutes_since_dose, doseSlot(check, doses), true); return <tr key={check.id} id={`check-${check.id}`}>
        <th scope="row">{onPick
          ? <button type="button" className="trends-row-link" onClick={() => onPick(checkDate(check))}>{weekday(checkDate(check))} {shortDate(checkDate(check))}, {clock(check.created_at)}<small>{when}</small></button>
          : <><strong>{clock(check.created_at)}</strong><small>{when}</small></>}</th>
        {COLUMNS.map(col => <td key={col.key} className={col.sep ? 'sep' : undefined}>{fmtMeasure(col.key, MEASURES[col.key].get(check))}</td>)}
      </tr> })}</tbody>
    </table></div>
    {checks.length > shown.length && <button type="button" className="trends-show-all" onClick={() => setAll(true)}>{t.showAll} {checks.length} {t.checks}</button>}
  </>
}
