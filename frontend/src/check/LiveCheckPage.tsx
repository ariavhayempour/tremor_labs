import { useEffect, useRef, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import type { SensorStream } from '../api/useSensorStream'
import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { Spectrum } from '../viz/Spectrum'
import { Waveform } from '../viz/Waveform'
import { isComplete, requiredRuns, steps, type CheckSession, type CheckStep, type TestStep } from './checkSession'
import { bandMessage } from './liveMessages'
import { liveTarget, useLiveTest } from './useLiveTest'
const t = copy.sensorCheck

interface Props { step: TestStep; session: CheckSession; stream: SensorStream; onDone: () => void; onSkip: () => void }
/** Sensor-mode test steps: each step records one backend test. */
export function LiveCheckPage(props: Props) {
  return <LiveTest {...props}/>
}

function Shell({ step, session, sidebar, output, status }: { step: CheckStep; session: CheckSession; sidebar: ReactNode; output: ReactNode; status: string }) {
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

function LiveTest({ step, session, stream, onDone, onSkip }: Props) {
  const complete = isComplete(session, step)
  const hand = session.hand ?? 'right'
  const live = useLiveTest({ step, checkId: session.checkId ?? 0, hand, stream, onDone })
  const running = live.phase === 'running'
  const busy = running || live.phase === 'starting' || live.phase === 'analyzing'
  const skipped = session.records[step]?.skipped === true
  const tap = step === 'tap'
  const error = live.error ? t.errors[live.error] : ''
  const startLabel = live.phase === 'starting' ? t.starting : live.phase === 'analyzing' ? t.analyzing
    : running ? (step === 'reach' ? `${t.recordingAttempt} ${live.attempt}` : copy.flow.recording)
    : live.phase === 'between' ? `${copy.flow.startAttempt} ${live.attempt + 1}`
    : live.phase === 'failed' ? t.retry : step === 'reach' ? `${copy.flow.startAttempt} 1` : copy.flow.start
  const sidebar = <>
    <div className="test-hand"><Icon name={tap ? 'tap' : 'sensor'} size={18}/>{t.testingHand}: {hand === 'left' ? copy.flow.leftHand : copy.flow.rightHand}</div>
    <div className="test-progress">
      <span>{complete ? (skipped ? t.skipped : copy.flow.complete) : running ? copy.flow.recording : live.phase === 'analyzing' ? t.analyzing : copy.flow.ready}</span>
      <strong>{complete ? <Icon name="check" size={20}/> : `${Math.max(0, Math.ceil(liveTarget(step) - live.elapsed))} ${copy.flow.seconds}`}</strong>
      <progress aria-label={copy.flow.progress} max={liveTarget(step)} value={complete ? liveTarget(step) : live.elapsed}/>
      {step === 'reach' && <small>{complete ? requiredRuns(step) : Math.max(0, live.attempt - (running ? 1 : 0))} / {requiredRuns(step)} {copy.flow.attempts}</small>}
    </div>
    {!complete && !tap && <button className="test-start" disabled={busy} onClick={() => void (live.phase === 'failed' ? (live.retry(), live.start()) : live.start())}><Icon name="play" size={17}/>{startLabel}</button>}
    {!complete && !busy && <button className="test-skip" onClick={onSkip}>{t.skip}</button>}
    {complete && <div className="test-completed"><Icon name="check" size={18}/>{skipped ? t.skipped : copy.flow.complete}</div>}
    {live.phase === 'between' && <p className="run-message" role="status">{t.betweenAttempts}</p>}
  </>
  const output = tap
    ? <div className="test-graph"><p>{t.tapPending}</p></div>
    : <>
        <div className="test-graph-toolbar"><span><Icon name={step === 'reach' ? 'reach' : 'wave'} size={18}/>{copy.flow.steps[step].visualization}</span><span className="muted">{running ? copy.flow.recording : copy.flow.ready}</span></div>
        {step === 'posture' && <div className="height-guide"><span>{copy.flow.handHeight}</span><strong>{live.position?.tof_mm != null ? `${Math.round(live.position.tof_mm)} ${copy.flow.mm}` : '—'}</strong><span className="height-band">{running ? bandMessage(live.position) : live.position ? `${t.target}: ${Math.round(live.position.band[0])}–${Math.round(live.position.band[1])} ${copy.flow.mm}` : ''}</span></div>}
        <div className="test-graph">
          <div className="chart-label">{step === 'reach' ? copy.flow.distance : copy.axis}</div>
          {step === 'reach'
            ? <Waveform buf={stream.tof} min={0} max={350} seconds={8} label={copy.flow.steps.reach.graphLabel}/>
            : <Waveform buf={stream.imu} center label={copy.flow.steps[step].graphLabel}/>}
          <div className="chart-bottom"><span>{step === 'reach' ? copy.flow.reachWindow : copy.sample}</span><span>{copy.timeAxis}</span></div>
        </div>
        {step !== 'reach' && <div className="test-graph"><div className="chart-label">{copy.spectrum.title}</div><Spectrum spectrum={stream.spectrum}/></div>}
      </>
  const status = error || (!stream.live && !complete ? t.errors.disconnected : complete ? copy.flow.readyToContinue : t.notice)
  return <Shell step={step} session={session} sidebar={sidebar} output={output} status={status}/>
}
