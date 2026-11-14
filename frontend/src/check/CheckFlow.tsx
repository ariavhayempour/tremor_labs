import './check.css'
import { useEffect, useState } from 'react'
import { Navigate, useParams } from 'react-router'
import type { useSensorStream } from '../api/useSensorStream'
import { CheckHeader } from './CheckHeader'
import { CheckPage } from './CheckPage'
import { CheckSummary } from './CheckSummary'
import { availableStep, finishRun, initialSession, readSession, steps, storageKey, type CheckStep, type Mode, type SignalPoint } from './checkSession'
export function CheckFlow({ stream }: { stream: ReturnType<typeof useSensorStream> }) {
  const { step = 'connect' } = useParams()
  const [session, setSession] = useState(readSession)
  useEffect(() => { try { sessionStorage.setItem(storageKey, JSON.stringify(session)) } catch { /* Keep the check usable when browser storage is disabled. */ } }, [session])
  const allowed = availableStep(session)
  const index = steps.indexOf(step as CheckStep)
  if (step !== 'complete' && index < 0) return <Navigate to="/check/connect" replace/>
  if ((step === 'complete' && allowed < 5) || index > allowed) return <Navigate to={`/check/${steps[Math.min(allowed, 4)]}`} replace/>
  function changeMode(mode: Mode) { setSession({ ...initialSession, mode }) }
  return <div className="check-app">
    <CheckHeader current={step} session={session}/>
    {step === 'complete'
      ? <CheckSummary session={session} onReset={() => setSession({ ...initialSession, mode: session.mode })}/>
      : <CheckPage key={`${step}-${session.mode}`} step={step as CheckStep} session={session} stream={stream} onMode={changeMode} onFinish={(samples?: SignalPoint[]) => setSession(current => finishRun(current, step as CheckStep, samples))}/>}
  </div>
}
