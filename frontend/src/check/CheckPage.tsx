import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import type { useSensorStream } from '../api/useSensorStream'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { Waveform } from '../viz/Waveform'
import { getHealth } from '../api/client'
import { isComplete, requiredRuns, runSeconds, steps, type CheckSession, type CheckStep, type Mode, type SignalPoint } from './checkSession'
import { useCheckRecording } from './useCheckRecording'
import { DeviceStatus } from './DeviceStatus'
export function CheckPage({ step, session, stream, onMode, onFinish }: { step: CheckStep; session: CheckSession; stream: ReturnType<typeof useSensorStream>; onMode: (mode: Mode) => void; onFinish: (samples?: SignalPoint[]) => void }) {
  const navigate = useNavigate()
  const text = copy.flow.steps[step]
  const demo = session.mode === 'demo'
  const complete = isComplete(session, step)
  const runs = session.records[step]?.runs ?? 0
  const recording = useCheckRecording(step, onFinish, session.records[step]?.samples)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const title = useRef<HTMLHeadingElement>(null)
  useEffect(() => { title.current?.focus({ preventScroll: true }); window.scrollTo(0, 0) }, [])
  const connectionTimer = useRef<number | undefined>(undefined)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false; clearTimeout(connectionTimer.current) } }, [])
  async function connect() {
    setChecking(true); setError('')
    if (demo) {
      connectionTimer.current = window.setTimeout(() => { onFinish(); setChecking(false) }, 700)
      return
    }
    try {
      await getHealth()
      if (alive.current) setError(copy.flow.sensorUnavailable)
    } catch { if (alive.current) setError(copy.offline) }
    finally { if (alive.current) setChecking(false) }
  }
  const index = steps.indexOf(step)
  const next = steps[index + 1]
  const active = recording.phase === 'running'
  const paused = recording.phase === 'paused'
  const waitingForNextRun = recording.phase === 'finished' && !complete
  const graphLabel = step === 'reach' ? copy.flow.distance : step === 'tap' ? copy.flow.fingerOpening : copy.axis
  const startLabel = step === 'connect' ? copy.flow.connect : step === 'reach' ? `${copy.flow.startAttempt} ${runs + 1}` : step === 'tap' ? runs === 0 ? copy.flow.startLeft : copy.flow.startRight : copy.flow.start
  return <>
    <main className="test-workspace">
      <aside className="test-sidebar">
        {step === 'connect' && <div className="check-mode" role="group" aria-label={copy.flow.source}>{(['demo', 'sensor'] as const).map(mode => <button key={mode} aria-pressed={session.mode === mode} disabled={checking} onClick={() => onMode(mode)}>{mode === 'demo' ? copy.flow.demo : copy.flow.sensor}</button>)}</div>}
        <section className="instruction-panel" aria-labelledby="test-title">
          <div className="test-step-kicker">{copy.flow.step} {index + 1} {copy.flow.of} 5</div>
          <h1 id="test-title" ref={title} tabIndex={-1}>{text.title}</h1>
          {text.instructions.map(paragraph => <p key={paragraph}>{paragraph}</p>)}
          {step === 'tap' && <div className="test-hand"><Icon name="tap" size={18}/>{runs === 0 ? copy.flow.leftHand : copy.flow.rightHand}</div>}
          {step !== 'connect' && <div className="test-progress">
            <span>{complete ? copy.flow.complete : active ? copy.flow.recording : paused ? copy.flow.paused : waitingForNextRun ? copy.flow.runComplete : copy.flow.ready}</span>
            <strong>{complete ? <Icon name="check" size={20}/> : `${Math.max(0, Math.ceil(runSeconds(step) - recording.elapsed))} ${copy.flow.seconds}`}</strong>
            <progress aria-label={copy.flow.progress} max={runSeconds(step)} value={complete ? runSeconds(step) : recording.elapsed}/>
            {(step === 'reach' || step === 'tap') && <small>{runs} / {requiredRuns(step)} {step === 'reach' ? copy.flow.attempts : copy.flow.hands}</small>}
          </div>}
          {!complete && <button className="test-start" disabled={checking || (step !== 'connect' && !demo)} onClick={step === 'connect' ? () => void connect() : active ? recording.pause : paused ? recording.resume : recording.start}>
            <Icon name={active ? 'pause' : paused ? 'play' : step === 'connect' ? 'connect' : 'play'} size={17}/>{checking ? copy.flow.connecting : active ? copy.flow.pause : paused ? copy.flow.resume : startLabel}
          </button>}
          {complete && <div className="test-completed"><Icon name="check" size={18}/>{copy.flow.complete}</div>}
          {waitingForNextRun && <p className="run-message" role="status">{step === 'tap' ? copy.flow.otherHand : copy.flow.nextReach}</p>}
        </section>
        <div className="test-source"><Icon name="shield" size={16}/><div><strong>{demo ? copy.flow.demo : copy.flow.sensor}</strong><span>{demo ? copy.flow.demoNotice : copy.flow.sensorNotice}</span></div></div>
        <Link className="test-exit" to="/overview"><Icon name="back" size={16}/>{copy.back}</Link>
      </aside>
      <div className="test-output">
        <section className="test-visualization" aria-labelledby="live-output-title">
          <div className="test-output-heading"><h2 id="live-output-title">{copy.sensor}</h2><span className="status"><span className={`dot ${active ? '' : 'gray'}`}/>{demo ? copy.flow.simulated : stream.connected ? copy.live : copy.disconnected}</span></div>
          {step === 'connect'
            ? <DeviceStatus demo={demo} connected={complete} checking={checking}/>
            : <>
                <div className="test-graph-toolbar"><span><Icon name={step === 'reach' ? 'reach' : step === 'tap' ? 'tap' : 'wave'} size={18}/>{text.visualization}</span><span className="muted">{complete ? copy.flow.complete : paused ? copy.flow.paused : active ? copy.flow.recording : copy.flow.ready}</span></div>
                {step === 'posture' && <div className="height-guide"><span>{copy.flow.handHeight}</span><strong>{recording.height} {copy.flow.mm}</strong><span className="height-band">{active || complete ? copy.flow.inRange : copy.flow.targetRange}</span></div>}
                {step === 'tap' && <div className="tap-metrics"><span>{runs === 0 || (recording.phase === 'finished' && runs === 1) ? copy.flow.leftHand : copy.flow.rightHand}</span><strong>{recording.taps}<small>{copy.flow.taps}</small></strong></div>}
                <div className="test-graph"><div className="chart-label">{graphLabel}</div><Waveform buf={demo ? recording.buffer : stream.imu} min={step === 'reach' ? 0 : step === 'tap' ? 0 : -2} max={step === 'reach' ? 350 : step === 'tap' ? 1 : 2} seconds={step === 'reach' ? 6 : 5} label={text.graphLabel}/><div className="chart-bottom"><span>{step === 'reach' ? copy.flow.reachWindow : copy.sample}</span><span>{copy.timeAxis}</span></div></div>
              </>}
          <div className="test-visualization-footer" role="status">{error || (complete ? copy.flow.stepSaved : demo ? copy.flow.demoNotice : copy.flow.sensorNotice)}</div>
        </section>
        <div className="test-next-row"><span className="test-next-status" aria-live="polite">{complete ? copy.flow.readyToContinue : step === 'connect' ? copy.flow.connectFirst : copy.flow.finishFirst}</span><button className={`test-continue ${complete ? 'is-ready' : ''}`} disabled={!complete} onClick={() => navigate(`/check/${next ?? 'complete'}`)}>{next ? `${copy.flow.continueTo} ${copy.flow.steps[next].label}` : copy.flow.viewSummary}<Icon name="arrow" size={18}/></button></div>
        <section className="test-activity"><h2>{copy.activity}</h2><ul>{steps.filter(s => session.records[s]).map(s => <li key={s}><Icon name={isComplete(session, s) ? 'check' : 'clock'} size={17}/><span>{copy.flow.steps[s].label}</span><small>{isComplete(session, s) ? copy.flow.complete : `${session.records[s]?.runs} / ${requiredRuns(s)}`}</small></li>)}{!Object.keys(session.records).length && <li className="muted"><Icon name="report" size={20}/>{copy.noChecks}</li>}</ul></section>
        <footer className="test-footer">{copy.footer}</footer>
      </div>
    </main>
  </>
}
