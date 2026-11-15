import type { CheckOut } from '../api/types'
import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { fmtMeasure, unitOf } from './format'
import { ALL_MEASURES, compare, meanOf } from './model'
const t = copy.trends

/** Every measure averaged over two sets of checks; the last column describes the change from the first set. */
export function MeasureTable({ sets, label }: { sets: [{ label: string; checks: CheckOut[] }, { label: string; checks: CheckOut[] }]; label: string }) {
  return <div className="trends-scroll" tabIndex={0} role="region" aria-label={label}><table className="trends-data trends-profile">
    <thead><tr><th scope="col">{t.measure}</th>{sets.map(s => <th scope="col" className="sep" key={s.label}>{s.label}<small>n={s.checks.length} {t.checks}</small></th>)}<th scope="col">{t.change}</th></tr></thead>
    <tbody>{ALL_MEASURES.filter(k => k !== 'tap').map(k => {
      const [ref, now] = sets.map(s => meanOf(s.checks, k)), change = compare(now, ref)
      return <tr key={k}><th scope="row">{t.measures[k]} <span className="muted">({unitOf(k)})</span></th>{[ref, now].map((v, i) => <td className="sep" key={i}>{fmtMeasure(k, v)}</td>)}
        <td>{change && <span className="trends-change"><Icon name={change === 'same' ? 'same' : change === 'higher' ? 'up' : 'down'} size={14}/>{t.compare[change]}</span>}</td></tr>
    })}</tbody>
  </table></div>
}
