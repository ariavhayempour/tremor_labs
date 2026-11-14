import { useEffect, useRef, useState } from 'react'
import { ApiError, led, markTest, startTest, stopTest, triggerDescent } from '../api/client'
import type { FailReason, Hand, PositionMsg } from '../api/types'
import type { SensorStream } from '../api/useSensorStream'
import { requiredRuns, runSeconds, type TestStep } from './checkSession'
export type LivePhase = 'ready' | 'starting' | 'running' | 'between' | 'analyzing' | 'failed'
export type LiveError = FailReason | 'test_active' | 'offline' | 'disconnected'
const TICK_MS = 100
const POSTURE_MAX_S = 75
export const liveTarget = (step: TestStep) => runSeconds(step)

/** Progress through the current run: wall-clock seconds, or in-band seconds for posture. */
export function runProgress(step: TestStep, wallSeconds: number, position: PositionMsg | null): number {
  return step === 'posture' ? position?.valid_seconds ?? 0 : wallSeconds
}
/** Whether the backend recording should stop now. */
export function shouldStop(step: TestStep, attempt: number, wallSeconds: number, progress: number): boolean {
  if (step === 'posture') return progress >= liveTarget(step) || wallSeconds >= POSTURE_MAX_S
  if (step === 'reach') return attempt >= requiredRuns(step) && wallSeconds >= liveTarget(step)
  return wallSeconds >= liveTarget(step)
}

/** Records one test step on the backend. Rest, posture and reach are recorded by the sensors. */
export function useLiveTest({ step, checkId, hand, stream, onDone }: { step: TestStep; checkId: number; hand: Hand; stream: SensorStream; onDone: () => void }) {
  const [phase, setPhase] = useState<LivePhase>('ready')
  const [elapsed, setElapsed] = useState(0)
  const [attempt, setAttempt] = useState(0)
  const [position, setPosition] = useState<PositionMsg | null>(null)
  const [error, setError] = useState<LiveError | null>(null)
  const testId = useRef<number | null>(null)
  const runStart = useRef(0)
  const phaseRef = useRef(phase)
  const attemptRef = useRef(0)
  const lastCount = useRef(-1)
  const live = useRef(stream.live)
  const done = useRef(onDone)
  useEffect(() => { phaseRef.current = phase }, [phase])
  useEffect(() => { live.current = stream.live }, [stream.live])
  useEffect(() => { done.current = onDone }, [onDone])
  useEffect(() => { led('hold') }, [])
  // Leaving mid-recording stops the backend test so the next start isn't blocked.
  useEffect(() => () => { if (testId.current !== null && ['running', 'between'].includes(phaseRef.current)) void stopTest(testId.current).catch(() => undefined) }, [])

  function fail(reason: LiveError) { setError(reason); setPhase('failed'); led('recording', 0) }
  function apiFailure(e: unknown) { fail(e instanceof ApiError && e.error === 'test_active' ? 'test_active' : 'offline') }

  async function finish(reason?: 'disconnected') {
    const id = testId.current
    if (id === null || phaseRef.current === 'analyzing') return
    phaseRef.current = 'analyzing'
    setPhase('analyzing')
    try {
      const outcome = await stopTest(id)
      testId.current = null
      if (outcome.status === 'done') { led('check'); led('recording', 0); setPhase('ready'); done.current() }
      else fail(reason ?? outcome.fail_reason ?? 'interrupted')
    } catch (e) { testId.current = null; apiFailure(e) }
  }

  function beginRun() {
    runStart.current = Date.now()
    lastCount.current = -1
    setElapsed(0)
    setPhase('running')
    led('recording', 1)
    if (step === 'reach' && stream.source === 'sim') void triggerDescent().catch(() => undefined)
  }

  async function start() {
    if (phase === 'starting' || phase === 'running' || phase === 'analyzing') return
    setError(null)
    if (phase === 'between' && testId.current !== null) {
      try { await markTest(testId.current) } catch (e) { apiFailure(e); return }
      attemptRef.current += 1; setAttempt(attemptRef.current)
      beginRun()
      return
    }
    setPhase('starting'); setPosition(null)
    try {
      testId.current = (await startTest(checkId, { type: step, hand })).test_id
      attemptRef.current = 1; setAttempt(1)
      beginRun()
    } catch (e) { apiFailure(e) }
  }

  useEffect(() => {
    if (phase !== 'running') return
    const timer = window.setInterval(() => {
      if (!live.current) { void finish('disconnected'); return }
      const wall = (Date.now() - runStart.current) / 1000
      const pos = stream.position.current
      const progress = runProgress(step, wall, pos)
      setElapsed(Math.min(progress, liveTarget(step)))
      if (step === 'posture') setPosition(pos)
      const left = Math.max(0, Math.ceil(liveTarget(step) - progress))
      if (left !== lastCount.current) { lastCount.current = left; led('countdown', left) }
      if (shouldStop(step, attemptRef.current, wall, progress)) void finish()
      else if (step === 'reach' && wall >= liveTarget(step)) { setPhase('between'); led('hold') }
    }, TICK_MS)
    return () => clearInterval(timer)
  }, [phase, step, stream.position])

  function retry() { setError(null); setPhase('ready'); setAttempt(0); attemptRef.current = 0; setElapsed(0) }
  return { phase, elapsed, attempt, position, error, start, retry }
}
