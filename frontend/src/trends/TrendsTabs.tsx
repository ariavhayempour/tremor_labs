import { copy } from '../copy'
export type TrendsView = 'simple' | 'detailed'

/** Switches between the plain summary and the full-detail view of the same data. */
export function TrendsTabs({ view, onChange }: { view: TrendsView; onChange: (view: TrendsView) => void }) {
  return <div className="trends-tabs" role="tablist" aria-label={copy.trends.view}>
    {(['simple', 'detailed'] as const).map(v => <button key={v} type="button" role="tab" aria-selected={view === v} onClick={() => onChange(v)}>{copy.trends[v]}</button>)}
  </div>
}
