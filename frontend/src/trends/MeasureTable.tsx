import type { CheckOut } from '../api/types'
import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { fmtMeasure, unitOf } from './format'
import { BOTH_HAND_MEASURES, compare, meanOf, type MeasureKey } from './model'
const t = copy.trends

/** Measures averaged over two sets of checks; the last column describes the second set against the first. */
export function MeasureTable({ sets, label, keys = BOTH_HAND_MEASURES, changeLabel = t.change }: { sets: [{ label: string; checks: CheckOut[] }, { label: string; checks: CheckOut[] }]; label: string; keys?: MeasureKey[]; changeLabel?: string }) {
  return <div className="trends-scroll" tabIndex={0} role="region" aria-label={label}><table className="trends-data trends-profile">
    <thead><tr><th scope="col">{t.measure}</th>{sets.map(s => <th scope="col" className="sep" key={s.label}>{s.label}<small>n={s.checks.length} {t.checks}</small></th>)}<th scope="col">{changeLabel}</th></tr></thead>
    <tbody>{keys.map(k => {
      const [ref, now] = sets.map(s => meanOf(s.checks, k)), change = compare(now, ref)
      return <tr key={k}><th scope="row">{t.measures[k]} <span className="muted">({unitOf(k)})</span></th>{[ref, now].map((v, i) => <td className="sep" key={i}>{fmtMeasure(k, v)}</td>)}
        <td>{change && <span className="trends-change"><Icon name={change === 'same' ? 'same' : change === 'higher' ? 'up' : 'down'} size={14}/>{t.compare[change]}</span>}</td></tr>
    })}</tbody>
  </table></div>
}
