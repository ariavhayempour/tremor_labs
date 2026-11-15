import { useEffect, useRef, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { isComplete, steps, type CheckSession, type CheckStep } from './checkSession'
const t = copy.sensorCheck

export function CheckShell({ step, session, sidebar, output, status }: { step: CheckStep; session: CheckSession; sidebar: ReactNode; output: ReactNode; status: string }) {
  const navigate = useNavigate()
  const title = useRef<HTMLHeadingElement>(null)
  useEffect(() => { title.current?.focus({ preventScroll: true }); window.scrollTo(0, 0) }, [])
  const index = steps.indexOf(step)
  const next = steps[index + 1]
  const complete = isComplete(session, step)
  const text = copy.flow.steps[step]
  return <main className="test-workspace">
    <aside className="test-sidebar">
      <section className="instruction-panel" aria-labelledby="test-title">
        <div className="test-step-kicker">{copy.flow.step} {index + 1} {copy.flow.of} 5</div>
        <h1 id="test-title" ref={title} tabIndex={-1}>{text.title}</h1>
        {text.instructions.map(p => <p key={p}>{p}</p>)}
        {sidebar}
      </section>
      <Link className="test-exit" to="/overview"><Icon name="back" size={16}/>{copy.back}</Link>
    </aside>
    <div className="test-output">
      <section className="test-visualization" aria-labelledby="live-output-title">
        <div className="test-output-heading"><h2 id="live-output-title">{copy.sensor}</h2></div>
        {output}
        <div className="test-next-row test-visualization-footer">
          <span className="test-next-status" role="status">{status}</span>
          <button className={`test-continue ${complete ? 'is-ready' : ''}`} disabled={!complete} onClick={() => navigate(`/check/${next ?? 'complete'}`)}><span className="continue-label">{next ? `${copy.flow.continueTo} ${copy.flow.steps[next].label}` : t.viewResults}<Icon name="arrow" size={18}/></span></button>
        </div>
      </section>
      <footer className="test-footer">{copy.footer}</footer>
    </div>
  </main>
}
