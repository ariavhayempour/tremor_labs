import { useNavigate } from 'react-router'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { steps, type CheckSession } from './checkSession'
export function CheckSummary({ session, onReset }: { session: CheckSession; onReset: () => void }) {
  const navigate = useNavigate()
  return <main className="check-summary"><span className="summary-check"><Icon name="check" size={32}/></span><h1>{copy.flow.summary}</h1><p>{session.mode === 'demo' ? copy.flow.summaryDemo : copy.flow.sensorNotice}</p><ol>{steps.map(step => <li key={step}><Icon name="check" size={18}/><span>{copy.flow.steps[step].label}</span><strong>{copy.flow.complete}</strong></li>)}</ol><button className="test-start" onClick={() => { onReset(); navigate('/check/connect') }}><Icon name="reset" size={18}/>{copy.flow.newCheck}</button><footer>{copy.footer}</footer></main>
}
