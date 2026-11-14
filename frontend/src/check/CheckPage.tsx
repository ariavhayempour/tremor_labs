import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import type { useSensorStream } from '../api/useSensorStream'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { Waveform } from '../viz/Waveform'
import { createCheck, getHealth, getSettings, led } from '../api/client'
import type { CheckInRequest, Hand, Health } from '../api/types'
import { MedicationPicker } from './MedicationPicker'
import { healthProblems } from './liveMessages'
import { isComplete, requiredRuns, runSeconds, steps, type CheckSession, type CheckStep, type Mode, type SignalPoint } from './checkSession'
import { useCheckRecording } from './useCheckRecording'
import { DeviceStatus } from './DeviceStatus'
/** Demo-mode steps, plus the connect step in both modes (sensor mode creates the backend check here). */
export function CheckPage({ step, session, stream, onMode, onFinish, onConnect }: { step: CheckStep; session: CheckSession; stream: ReturnType<typeof useSensorStream>; onMode: (mode: Mode) => void; onFinish: (samples?: SignalPoint[]) => void; onConnect: (checkId: number, hand: Hand, minutes: number | null) => void }) {
  const navigate = useNavigate()
  const text = copy.flow.steps[step]
  const demo = session.mode === 'demo'
  const complete = isComplete(session, step)
  const runs = session.records[step]?.runs ?? 0
  const recording = useCheckRecording(step, onFinish, session.records[step]?.samples)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [health, setHealth] = useState<Health | null>(null)
  const [creating, setCreating] = useState(false)
  const ready = !demo && health !== null && healthProblems(health).length === 0
  useEffect(() => { if (step === 'connect') led('idle') }, [step])
  const [detectedCount, setDetectedCount] = useState(complete ? 3 : 0)
  const [celebrating, setCelebrating] = useState(false)
  const celebrationTimer = useRef<number | undefined>(undefined)
  const title = useRef<HTMLHeadingElement>(null)
  useEffect(() => { title.current?.focus({ preventScroll: true }); window.scrollTo(0, 0) }, [])
  const connectionTimer = useRef<number | undefined>(undefined)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false; clearTimeout(connectionTimer.current); clearTimeout(celebrationTimer.current) } }, [])
  function changeMode(mode: Mode) {
    if (mode === session.mode) return
    clearTimeout(connectionTimer.current)
    clearTimeout(celebrationTimer.current)
    setChecking(false); setError(''); setDetectedCount(0); setCelebrating(false); setHealth(null)
    onMode(mode)
  }
  async function connect() {
    if (checking || complete) return
    setChecking(true); setError(''); setDetectedCount(0); setCelebrating(false)
    if (demo) {
      let detected = 0
      function detectNext() {
        if (!alive.current) return
        detected += 1
        setDetectedCount(detected)
        if (detected === 3) {
          onFinish(); setChecking(false); setCelebrating(true)
          celebrationTimer.current = window.setTimeout(() => setCelebrating(false), 1600)
        } else connectionTimer.current = window.setTimeout(detectNext, 400)
      }
      connectionTimer.current = window.setTimeout(detectNext, 400)
      return
    }
    try {
      const h = await getHealth()
      if (alive.current) { setHealth(h); setError(healthProblems(h)[0] ?? '') }
    } catch { if (alive.current) { setHealth(null); setError(copy.offline) } }
    finally { if (alive.current) setChecking(false) }
  }
  async function pick(body: CheckInRequest) {
    setCreating(true); setError('')
    try {
      const hand = await getSettings().then(s => s.tested_hand, () => 'right' as const)
      const created = await createCheck(body)
      if (alive.current) onConnect(created.check_id, hand, created.minutes_since_dose)
    } catch { if (alive.current) setError(copy.offline) }
    finally { if (alive.current) setCreating(false) }
  }
  const deviceRows = !demo && health ? [
    { detected: health.connected && health.sensors_detected.movement, status: health.connected && health.sensors_detected.movement ? copy.flow.backendReady : copy.flow.notConnected },
    { detected: health.connected && health.sensors_detected.distance, status: health.connected && health.sensors_detected.distance ? copy.flow.backendReady : copy.flow.notConnected },
    { detected: false, status: copy.sensorCheck.cameraLater },
  ] : undefined
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
        {step === 'connect' && <div className="check-mode" data-mode={session.mode} role="group" aria-label={copy.flow.source}>{(['demo', 'sensor'] as const).map(mode => <button key={mode} aria-pressed={session.mode === mode} disabled={checking} onClick={() => changeMode(mode)}>{mode === 'demo' ? copy.flow.demo : copy.flow.sensor}</button>)}</div>}
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
          {!complete && <button className="test-start" disabled={checking || creating || (step !== 'connect' && !demo)} onClick={step === 'connect' ? () => void connect() : active ? recording.pause : paused ? recording.resume : recording.start}>
            <Icon name={active ? 'pause' : paused ? 'play' : step === 'connect' ? 'connect' : 'play'} size={17}/>{checking ? copy.flow.connecting : active ? copy.flow.pause : paused ? copy.flow.resume : ready ? copy.sensorCheck.checkSensors : startLabel}
          </button>}
          {complete && <div className="test-completed"><Icon name="check" size={18}/>{copy.flow.complete}</div>}
          {waitingForNextRun && <p className="run-message" role="status">{step === 'tap' ? copy.flow.otherHand : copy.flow.nextReach}</p>}
        </section>
        <Link className="test-exit" to="/overview"><Icon name="back" size={16}/>{copy.back}</Link>
      </aside>
      <div className="test-output">
        <section className="test-visualization" aria-labelledby="live-output-title">
          <div className="test-output-heading"><h2 id="live-output-title">{copy.sensor}</h2><span className="status"><span className={`dot ${active ? '' : 'gray'}`}/>{demo ? copy.flow.simulated : stream.connected ? copy.live : copy.disconnected}</span></div>
          {step === 'connect'
            ? ready && !complete
              ? <><p className="devices-ready"><span><Icon name="check" size={18}/></span>{copy.flow.devicesReady}</p><MedicationPicker busy={creating} onPick={body => void pick(body)}/></>
              : <DeviceStatus demo={demo} connected={complete} checking={checking} detectedCount={detectedCount} celebrating={celebrating} rows={deviceRows}/>
            : <>
                <div className="test-graph-toolbar"><span><Icon name={step === 'reach' ? 'reach' : step === 'tap' ? 'tap' : 'wave'} size={18}/>{text.visualization}</span><span className="muted">{complete ? copy.flow.complete : paused ? copy.flow.paused : active ? copy.flow.recording : copy.flow.ready}</span></div>
                {step === 'posture' && <div className="height-guide"><span>{copy.flow.handHeight}</span><strong>{recording.height} {copy.flow.mm}</strong><span className="height-band">{active || complete ? copy.flow.inRange : copy.flow.targetRange}</span></div>}
                {step === 'tap' && <div className="tap-metrics"><span>{runs === 0 || (recording.phase === 'finished' && runs === 1) ? copy.flow.leftHand : copy.flow.rightHand}</span><strong>{recording.taps}<small>{copy.flow.taps}</small></strong></div>}
                <div className="test-graph"><div className="chart-label">{graphLabel}</div><Waveform buf={demo ? recording.buffer : stream.imu} min={step === 'reach' ? 0 : step === 'tap' ? 0 : -2} max={step === 'reach' ? 350 : step === 'tap' ? 1 : 2} seconds={step === 'reach' ? 6 : 5} label={text.graphLabel}/><div className="chart-bottom"><span>{step === 'reach' ? copy.flow.reachWindow : copy.sample}</span><span>{copy.timeAxis}</span></div></div>
              </>}
          <div className="test-next-row test-visualization-footer">
            <span className="test-next-status" role="status">{error || (complete ? copy.flow.readyToContinue : demo ? copy.flow.demoNotice : copy.sensorCheck.notice)}</span>
            <button className={`test-continue ${complete ? 'is-ready' : ''}`} disabled={!complete} onClick={() => navigate(`/check/${next ?? 'complete'}`)}><span className="continue-label">{next ? `${copy.flow.continueTo} ${copy.flow.steps[next].label}` : copy.flow.viewSummary}<Icon name="arrow" size={18}/></span></button>
          </div>
        </section>
        <footer className="test-footer">{copy.footer}</footer>
      </div>
    </main>
  </>
}
