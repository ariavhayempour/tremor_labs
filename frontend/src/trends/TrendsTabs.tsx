import { copy } from '../copy'
export type TrendsView = 'simple' | 'detailed' | 'compare'
const ALL_VIEWS: readonly TrendsView[] = ['simple', 'detailed', 'compare']

/** Switches between the plain summary, the full-detail view and the left/right comparison. */
export function TrendsTabs({ view, onChange, views = ALL_VIEWS }: { view: TrendsView; onChange: (view: TrendsView) => void; views?: readonly TrendsView[] }) {
  return <div className="trends-tabs" role="tablist" aria-label={copy.trends.view}>
    {views.map(v => <button key={v} type="button" role="tab" aria-selected={view === v} onClick={() => onChange(v)}>{copy.trends.tabs[v]}</button>)}
  </div>
}
