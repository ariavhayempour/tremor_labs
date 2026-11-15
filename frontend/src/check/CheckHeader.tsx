import { Link } from 'react-router'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { availableStep, isComplete, steps, type CheckSession, type CheckStep } from './checkSession'
export function CheckHeader({ current, session }: { current: string; session: CheckSession }) {
  return <header className="check-header">
    <Link className="check-brand" to="/overview"><span className="check-brand-mark"><Icon name="wave" size={21}/></span>{copy.brand}</Link>
    <nav className="check-navigation" aria-label={copy.flow.navigation}>
      {steps.map((step: CheckStep, index) => {
        const content = <><span className="check-step-number">{isComplete(session, step) ? <Icon name="check" size={14}/> : index + 1}</span><span>{copy.flow.steps[step].label}</span></>
        const active = current === step
        return index <= availableStep(session)
          ? <Link key={step} className={`check-tab ${active ? 'is-current' : ''} ${isComplete(session, step) ? 'is-done' : ''}`} to={`/check/${step}`} aria-current={active ? 'step' : undefined}>{content}</Link>
          : <span key={step} className="check-tab is-locked" aria-disabled="true">{content}</span>
      })}
    </nav>
    <Link className="check-history hover-sweep" to="/dashboard"><Icon name="history" size={17}/>{copy.home.testHistory}</Link>
  </header>
}
