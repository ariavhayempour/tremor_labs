import { Link } from 'react-router'
import type { CheckOut, DoseOut } from '../api/types'
import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { afterDose, clock, fmt, fmtMeasure } from './format'
import { doseSlot, MEASURES, resultOf } from './model'
const t = copy.trends

/** The checks of one day in plain terms: the four headline results with one supporting detail each. */
export function DayCheckList({ checks, doses, linkResults }: { checks: CheckOut[]; doses: DoseOut[]; linkResults: boolean }) {
  return <table className="trends-checks">
    <thead><tr><th scope="col">{t.time}</th><th scope="col">{t.restCol}<small>{t.units.score}</small></th><th scope="col">{t.postureCol}<small>{t.units.score}</small></th><th scope="col">{t.reachCol}<small>{t.units.mm}</small></th><th scope="col">{t.tapSpeedChart}<small>{t.leftShort} / {t.rightShort}, {t.units.taps}</small></th><th scope="col"><span className="trends-vh">{t.fullResults}</span></th></tr></thead>
    <tbody>{checks.map(c => {
      const rest = resultOf(c, 'rest'), posture = resultOf(c, 'posture'), reach = resultOf(c, 'reach')
      const cv = [resultOf(c, 'tap', 'left')?.rhythm_cv, resultOf(c, 'tap', 'right')?.rhythm_cv].filter((v): v is number => typeof v === 'number')
      return <tr key={c.id} id={`check-${c.id}`}>
        <td className="when"><span className="big">{clock(c.created_at)}</span><small>{afterDose(c.minutes_since_dose, doseSlot(c, doses))}</small></td>
        <td data-label={t.restCol}><span className="big">{fmtMeasure('rest', MEASURES.rest.get(c))}</span><small>{rest?.peak_hz ? `${rest.peak_hz.toFixed(1)} ${t.rhythmUnit}` : t.noRhythm}</small></td>
        <td data-label={t.postureCol}><span className="big">{fmtMeasure('posture', MEASURES.posture.get(c))}</span><small>{fmt(posture?.valid_seconds, 1)} {t.heldInPlace}</small></td>
        <td data-label={t.reachCol}><span className="big">{fmtMeasure('reach', MEASURES.reach.get(c))}</span><small>{fmt(reach?.wobble_ratio, 1)}{t.endWobble}</small></td>
        <td data-label={t.tapSpeedChart}><span className="big">{fmtMeasure('tapL', MEASURES.tapL.get(c))} / {fmtMeasure('tapR', MEASURES.tapR.get(c))}</span><small>{t.rhythmVaries} {cv.length ? Math.round(cv.reduce((a, b) => a + b, 0) / cv.length * 100) : '—'}%</small></td>
        <td className="go">{linkResults && <Link to={`/results/${c.id}`}>{t.fullResults}<Icon name="arrow" size={16}/></Link>}</td>
      </tr>
    })}</tbody>
  </table>
}
