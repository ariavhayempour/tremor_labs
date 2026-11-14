import { Link } from 'react-router'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { ResultCard } from './ResultCard'
import type { CheckSession } from './checkSession'

const resultSteps = ['rest', 'posture', 'reach', 'tap'] as const
export function CheckResults({ session }: { session: CheckSession }) {
  return <main className="check-results">
    <div className="results-heading"><div><h1>{copy.flow.resultsTitle}</h1><p>{session.mode === 'demo' ? copy.flow.resultDemo : copy.flow.complete}</p></div><Link className="summary-home back-link" to="/check/complete"><Icon name="back" size={16}/>{copy.flow.backSummary}</Link></div>
    <div className="results-grid">{resultSteps.map(step => {
      const record = session.records[step]
      return record ? <ResultCard key={step} step={step} record={record}/> : null
    })}</div>
    <div className="results-bottom"><Link className="summary-home back-link" to="/"><Icon name="back" size={16}/>{copy.back}</Link><footer>{copy.footer}</footer></div>
  </main>
}
