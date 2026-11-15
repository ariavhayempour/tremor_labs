import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router'
import { recordCompletedCheck } from '../home/homeStore'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import type { Hand } from '../api/types'
import { otherHand, steps, type CheckSession } from './checkSession'

export function CheckSummary({ session, onReset }: { session: CheckSession; onReset: (hand: Hand) => void }) {
  const navigate = useNavigate()
  const next = otherHand(session.hand)
  useEffect(() => { recordCompletedCheck() }, [])
  return <main className="check-summary">
    <span className="summary-check"><Icon name="check" size={28}/></span>
    <h1>{copy.flow.summary}</h1>
    <p className="summary-hand">{copy.flow.checkedHand[session.hand]}</p>
    <p>{session.mode === 'demo' ? copy.flow.summaryDemo : copy.flow.sensorNotice}</p>
    <ol>{steps.map(step => <li key={step}><Icon name="check" size={17}/><span>{copy.flow.steps[step].label}</span><strong>{copy.flow.complete}</strong></li>)}</ol>
    <div className="summary-actions">
      <Link className="test-start hover-sweep" to="/check/results">{copy.flow.seeResult}<Icon name="arrow" size={18}/></Link>
      <button className="summary-restart hover-sweep" onClick={() => { onReset(next); navigate('/check/connect') }}><Icon name="reset" size={17}/>{copy.flow.checkHand[next]}</button>
    </div>
    <Link className="summary-home back-link" to="/"><Icon name="back" size={16}/>{copy.back}</Link>
    <footer>{copy.footer}</footer>
  </main>
}
