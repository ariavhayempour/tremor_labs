import type { CheckOut } from '../api/types'
import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { fmtMeasure, unitAfter, unitOf } from './format'
import { compare, meanOf, type MeasureKey } from './model'
const t = copy.trends
const KEYS: MeasureKey[] = ['rest', 'posture', 'reach', 'tap']

/** The four headline tests for a set of checks beside the first-week average, with the change described in words. */
export function CompareStrip({ checks, reference }: { checks: CheckOut[]; reference: CheckOut[] }) {
  return <div className="trends-compare">{KEYS.map(k => {
    const v = meanOf(checks, k), r = meanOf(reference, k), change = compare(v, r)
    return <div key={k}>
      <h3>{t.measures[k]}</h3>
      <p className="value">{fmtMeasure(k, v)}<small>{unitOf(k)}</small></p>
      <p className="ref">{t.firstWeek} {fmtMeasure(k, r)}{unitAfter(k)}</p>
      {change && <span className="trends-pill"><Icon name={change === 'same' ? 'same' : change === 'higher' ? 'up' : 'down'} size={15}/>{t.compare[change]}</span>}
    </div>
  })}</div>
}
