import { copy } from '../copy'
import { fmtMeasure, unitAfter } from './format'
import { compare, meanOf, type MeasureKey } from './model'
import type { TrendsData } from './useTrendsData'
const t = copy.trends

/** The last 3 days' average for one measure, described against the first week. */
export function StatLine({ k, data }: { k: MeasureKey; data: TrendsData }) {
  const v = meanOf(data.recent, k), r = meanOf(data.reference, k), change = compare(v, r)
  return <p className="trends-stat">{t.last3} <strong>{fmtMeasure(k, v)}{unitAfter(k)}</strong>{change && <span> · {t.compareInline[change]} {t.firstWeekLower} ({fmtMeasure(k, r)}{unitAfter(k)})</span>}</p>
}
