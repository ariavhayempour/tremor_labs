import type { SensorStream } from '../api/useSensorStream'
import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { Spectrum } from '../viz/Spectrum'
import { Waveform } from '../viz/Waveform'
import { isComplete, requiredRuns, type CheckSession, type TestStep } from './checkSession'
import { bandMessage } from './liveMessages'
import { liveTarget, useLiveTest } from './useLiveTest'
import { CheckShell } from './CheckShell'
import { TapTest } from '../tap/TapTest'
const t = copy.sensorCheck

interface Props { step: TestStep; session: CheckSession; stream: SensorStream; onDone: () => void; onSkip: () => void; onTapDone: () => void }
/** Sensor-mode steps; tap records a separate backend test for each hand. */
export function LiveCheckPage(props: Props) {
  return props.step === 'tap' ? <TapTest session={props.session} onDone={props.onTapDone} onSkip={props.onSkip}/> : <LiveTest {...props}/>
}


function LiveTest({ step, session, stream, onDone, onSkip }: Props) {
  const complete = isComplete(session, step)
  const hand = session.hand ?? 'right'
  const live = useLiveTest({ step, checkId: session.checkId ?? 0, hand, stream, onDone })
  const running = live.phase === 'running'
  const busy = running || live.phase === 'starting' || live.phase === 'analyzing'
  const skipped = session.records[step]?.skipped === true
  const error = live.error ? t.errors[live.error] : ''
  const startLabel = live.phase === 'starting' ? t.starting : live.phase === 'analyzing' ? t.analyzing
    : running ? (step === 'reach' ? `${t.recordingAttempt} ${live.attempt}` : copy.flow.recording)
    : live.phase === 'between' ? `${copy.flow.startAttempt} ${live.attempt + 1}`
    : live.phase === 'failed' ? t.retry : step === 'reach' ? `${copy.flow.startAttempt} 1` : copy.flow.start
  const sidebar = <>
    <div className="test-hand"><Icon name="sensor" size={18}/>{t.testingHand}: {hand === 'left' ? copy.flow.leftHand : copy.flow.rightHand}</div>
    <div className="test-progress">
      <span>{complete ? (skipped ? t.skipped : copy.flow.complete) : running ? copy.flow.recording : live.phase === 'analyzing' ? t.analyzing : copy.flow.ready}</span>
      <strong>{complete ? <Icon name="check" size={20}/> : `${Math.max(0, Math.ceil(liveTarget(step) - live.elapsed))} ${copy.flow.seconds}`}</strong>
      <progress aria-label={copy.flow.progress} max={liveTarget(step)} value={complete ? liveTarget(step) : live.elapsed}/>
      {step === 'reach' && <small>{complete ? requiredRuns(step) : Math.max(0, live.attempt - (running ? 1 : 0))} / {requiredRuns(step)} {copy.flow.attempts}</small>}
    </div>
    {!complete && <button className="test-start" disabled={busy} onClick={() => void (live.phase === 'failed' ? (live.retry(), live.start()) : live.start())}><Icon name="play" size={17}/>{startLabel}</button>}
    {!complete && !busy && <button className="test-skip" onClick={onSkip}>{t.skip}</button>}
    {complete && <div className="test-completed"><Icon name="check" size={18}/>{skipped ? t.skipped : copy.flow.complete}</div>}
    {live.phase === 'between' && <p className="run-message" role="status">{t.betweenAttempts}</p>}
  </>
  const output = <>
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
  return <CheckShell step={step} session={session} sidebar={sidebar} output={output} status={status}/>
}
