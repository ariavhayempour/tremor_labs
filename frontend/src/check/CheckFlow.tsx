import './check.css'
import { useEffect, useState } from 'react'
import { Navigate, useParams } from 'react-router'
import type { SensorStream } from '../api/useSensorStream'
import { CheckHeader } from './CheckHeader'
import { CheckPage } from './CheckPage'
import { CheckSummary } from './CheckSummary'
import { CheckResults } from './CheckResults'
import { LiveCheckPage } from './LiveCheckPage'
import { availableStep, chooseHand, connectCheck, defaultMode, finishRun, freshSession, isComplete, readSession, skipStep, steps, storageKey, type CheckStep, type Mode, type SignalPoint } from './checkSession'
export function CheckFlow({ stream }: { stream: SensorStream }) {
  const { step = 'connect' } = useParams()
  const [session, setSession] = useState(() => readSession(defaultMode))
  useEffect(() => { try { sessionStorage.setItem(storageKey, JSON.stringify(session)); if (!Object.keys(session.records).length) sessionStorage.removeItem('tremor-history-recorded') } catch { /* Keep the check usable when browser storage is disabled. */ } }, [session])
  const allowed = availableStep(session)
  const index = steps.indexOf(step as CheckStep)
  const reviewPage = step === 'complete' || step === 'results'
  if (!reviewPage && index < 0) return <Navigate to="/check/connect" replace/>
  if ((reviewPage && allowed < 5) || index > allowed) return <Navigate to={`/check/${steps[Math.min(allowed, 4)]}`} replace/>
  if (reviewPage && session.mode === 'sensor' && session.checkId !== undefined) return <Navigate to={`/results/${session.checkId}`} replace/>
  function changeMode(mode: Mode) { setSession(s => freshSession(mode, s.hand)) }
  const current = step as CheckStep
  // A sensor-mode step completes all its runs at once: the backend stores one test per step.
  const completeStep = () => setSession(s => { let next = s; while (!isComplete(next, current)) { const after = finishRun(next, current); if (after === next) break; next = after } return next })
  return <div className="check-app">
    <CheckHeader current={step} session={session}/>
    {step === 'complete'
      ? <CheckSummary session={session} onReset={hand => setSession(freshSession(session.mode, hand))}/>
      : step === 'results' ? <CheckResults session={session}/>
      : session.mode === 'sensor' && current !== 'connect'
        ? <LiveCheckPage key={step} step={current} session={session} stream={stream}
            onDone={completeStep} onTapDone={() => setSession(s => finishRun(s, 'tap'))} onSkip={() => setSession(s => skipStep(s, current))}/>
        : <CheckPage key={step} step={current} session={session} stream={stream} onMode={changeMode}
            onHand={hand => setSession(s => chooseHand(s, hand))}
            onConnect={(checkId, minutes) => setSession(s => connectCheck(s, checkId, minutes))}
            onFinish={(samples?: SignalPoint[]) => setSession(s => finishRun(s, current, samples))}/>}
  </div>
}
