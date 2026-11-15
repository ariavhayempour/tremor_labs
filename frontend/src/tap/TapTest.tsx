import { useEffect, useRef, useState } from 'react'
import { ApiError, led, sendTapData, startTest } from '../api/client'
import type { TapFrame } from '../api/types'
import { CheckShell } from '../check/CheckShell'
import { isComplete, type CheckSession } from '../check/checkSession'
import { copy } from '../copy'
import { createHandLandmarker } from './handLandmarker'
import { LiveTapCounter, opening, tapLandmarks } from './signal'
import './tap.css'

type Phase = 'ready' | 'loading' | 'preparing' | 'recording' | 'saving' | 'failed'
const c = copy.tap
export function TapTest({ session, onDone, onSkip }: { session: CheckSession; onDone: () => void; onSkip: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const overlay = useRef<HTMLCanvasElement>(null)
  const cancel = useRef<(() => void) | null>(null)
  const locked = useRef(false)
  const [phase, setPhase] = useState<Phase>('ready')
  const [seconds, setSeconds] = useState(0)
  const [count, setCount] = useState(0)
  const [missing, setMissing] = useState(false)
  const [error, setError] = useState('')
  const runs = session.records.tap?.runs ?? 0
  const hand = runs === 0 ? 'left' : 'right'
  const complete = isComplete(session, 'tap')
  const completionLabel = session.records.tap?.skipped ? copy.sensorCheck.skipped : copy.flow.complete
  const busy = ['loading', 'preparing', 'recording', 'saving'].includes(phase)
  useEffect(() => () => { cancel.current?.() }, [])

  async function start() {
    if (locked.current || complete) return
    locked.current = true
    setPhase('loading'); setError(''); setCount(0); setSeconds(0); setMissing(false)
    let disposed = false
    let stream: MediaStream | undefined
    let detector: Awaited<ReturnType<typeof createHandLandmarker>> | undefined
    let testId: number | null = null
    let frameId = 0
    let timer = 0
    let stage: Phase = 'loading'
    const release = () => {
      cancelAnimationFrame(frameId); clearTimeout(timer)
      stream?.getTracks().forEach(track => track.stop())
      detector?.close(); detector = undefined
      if (video.current) video.current.srcObject = null
      overlay.current?.getContext('2d')?.clearRect(0, 0, 640, 480)
      led('recording', 0)
    }
    const abandon = () => {
      if (testId !== null) { void sendTapData(testId, { frames: [] }).catch(() => undefined); testId = null }
    }
    cancel.current = () => { disposed = true; release(); abandon(); locked.current = false }
    const fail = (message: string) => {
      if (disposed) return
      release(); abandon(); locked.current = false; setPhase('failed'); setError(message)
    }
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('camera')
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false })
      if (disposed) { release(); return }
      video.current!.srcObject = stream
      await video.current!.play()
      detector = await createHandLandmarker()
      if (disposed) { release(); return }
      testId = (await startTest(session.checkId!, { type: 'tap', hand })).test_id
      if (disposed) { abandon(); release(); return }
      const frames: TapFrame[] = []
      const counter = new LiveTapCounter()
      const startsAt = performance.now() + 3000
      let lastVideoTime = -1
      let lastHand = startsAt
      stage = 'preparing'; setPhase('preparing'); setSeconds(3)
      async function finish() {
        if (disposed || stage === 'saving') return
        stage = 'saving'; setPhase('saving'); setSeconds(10)
        release()
        const id = testId!
        // This request finalizes the tap test; never submit it twice on unmount.
        testId = null
        try {
          const result = await sendTapData(id, { frames })
          if (disposed) return
          if (result.status !== 'done') { fail(copy.sensorCheck.errors[result.fail_reason ?? 'interrupted']); return }
          locked.current = false; setPhase('ready'); led('check'); onDone()
        } catch { fail(copy.sensorCheck.errors.offline) }
      }
      timer = window.setTimeout(() => void finish(), 13000)
      function tick(now: number) {
        if (disposed || !detector || !video.current) return
        try {
          const elapsed = (now - startsAt) / 1000
          if (elapsed >= 10) { void finish(); return }
          if (elapsed >= 0 && stage === 'preparing') { stage = 'recording'; setPhase('recording'); led('recording', 1) }
          setSeconds(elapsed < 0 ? Math.ceil(-elapsed) : elapsed)
          if (video.current.readyState >= 2 && video.current.currentTime !== lastVideoTime) {
            lastVideoTime = video.current.currentTime
            const result = detector.detectForVideo(video.current, now)
            const lm = tapLandmarks(result.landmarks[0])
            if (lm) lastHand = now
            setMissing(now - lastHand > 1000)
            const canvas = overlay.current
            const ctx = canvas?.getContext('2d')
            if (ctx && canvas) {
              ctx.clearRect(0, 0, canvas.width, canvas.height)
              if (lm) {
                ctx.strokeStyle = '#68c4ff'; ctx.fillStyle = '#ffe45c'; ctx.lineWidth = 4
                ctx.beginPath(); ctx.moveTo(lm[1][0] * 640, lm[1][1] * 480); ctx.lineTo(lm[2][0] * 640, lm[2][1] * 480); ctx.stroke()
                for (const [x, y] of lm) { ctx.beginPath(); ctx.arc(x * 640, y * 480, 7, 0, Math.PI * 2); ctx.fill() }
              }
            }
            if (elapsed >= 0) { frames.push({ t_ms: now, lm }); setCount(counter.push(opening(lm))) }
          }
          frameId = requestAnimationFrame(tick)
        } catch { fail(c.trackingError) }
      }
      frameId = requestAnimationFrame(tick)
    } catch (e) {
      fail(e instanceof ApiError ? copy.sensorCheck.errors.offline : e instanceof DOMException && ['NotAllowedError', 'NotFoundError', 'NotReadableError'].includes(e.name) ? c.cameraDenied : c.setupError)
    }
  }
  const status = error || (complete ? copy.flow.readyToContinue : missing ? c.moveIntoLight : phase === 'preparing' ? `${c.getReady} ${seconds}` : phase === 'saving' ? copy.sensorCheck.analyzing : c.local)
  const sidebar = <>
    <div className="test-hand">{copy.sensorCheck.testingHand}: {hand === 'left' ? copy.flow.leftHand : copy.flow.rightHand}</div>
    <div className="test-progress"><span>{phase === 'recording' ? copy.flow.recording : phase === 'preparing' ? c.getReady : copy.flow.ready}</span><strong>{complete ? completionLabel : `${phase === 'preparing' ? seconds : Math.max(0, Math.ceil(10 - seconds))} s`}</strong><progress aria-label={copy.flow.progress} max={10} value={complete ? 10 : phase === 'recording' ? seconds : 0}/><small>{runs} / 2 {copy.flow.hands}</small></div>
    {!complete && <button className="test-start hover-sweep" disabled={busy} onClick={() => void start()}>{phase === 'loading' ? c.loading : phase === 'saving' ? copy.sensorCheck.analyzing : phase === 'failed' ? copy.sensorCheck.retry : hand === 'left' ? copy.flow.startLeft : copy.flow.startRight}</button>}
    {!complete && <button className="test-skip" disabled={busy} onClick={onSkip}>{copy.sensorCheck.skip}</button>}
    {runs === 1 && !busy && <p>{copy.flow.otherHand}</p>}
  </>
  const output = <div className="tap-output"><div className="tap-camera"><video ref={video} muted playsInline aria-label={c.preview}/><canvas ref={overlay} width={640} height={480} aria-hidden="true"/>{!busy && !complete && <span className="tap-camera-idle">{c.cameraIdle}</span>}</div><p>{count} {c.taps}</p>{missing && <p role="alert">{c.moveIntoLight}</p>}{error && <p role="alert">{error}</p>}</div>
  return <CheckShell step="tap" session={session} sidebar={sidebar} output={output} status={status}/>
}
