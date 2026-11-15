import { useEffect, useRef, useState } from 'react'
import { RingBuf } from '../viz/ringbuf'
import { COUNTDOWN_S, runSeconds, type CheckStep, type SignalPoint } from './checkSession'
export type RecordingPhase = 'ready' | 'countdown' | 'running' | 'paused' | 'finished'
export function useCheckRecording(step: CheckStep, onFinish: (samples?: SignalPoint[]) => void, initialSamples?: SignalPoint[]) {
  const buffer = useRef(new RingBuf(1500, 1))
  const savedSamples = useRef(initialSamples)
  useEffect(() => { buffer.current.clear(); savedSamples.current?.forEach(point => buffer.current.push(point.t, [point.value])) }, [])
  const [phase, setPhase] = useState<RecordingPhase>('ready')
  const [elapsed, setElapsed] = useState(0)
  const [countdown, setCountdown] = useState(0)
  const [height, setHeight] = useState(220)
  const [taps, setTaps] = useState(0)
  const finish = useRef(onFinish)
  useEffect(() => { finish.current = onFinish }, [onFinish])
  const elapsedRef = useRef(0)
  useEffect(() => {
    if (phase !== 'countdown') return
    const timer = window.setTimeout(() => { if (countdown > 1) setCountdown(countdown - 1); else setPhase('running') }, 1000)
    return () => clearTimeout(timer)
  }, [phase, countdown])
  useEffect(() => {
    if (phase !== 'running') return
    let previous = Date.now()
    const timer = window.setInterval(() => {
      const now = Date.now()
      const delta = (now - previous) / 1000
      previous = now
      if (document.hidden) { setPhase('paused'); return }
      const before = elapsedRef.current
      const after = Math.min(before + delta, runSeconds(step))
      for (let t = before; t < after; t += 0.01) {
        const value = step === 'reach'
          ? 280 - 245 * (t / 6) + (t > 4.5 ? 2.5 : 0.5) * Math.sin(t * 28)
          : step === 'tap' ? 0.52 + 0.4 * Math.sin(t * Math.PI * 6)
          : 0.3 * Math.sin(t * Math.PI * 10) + 0.015 * Math.sin(t * 91)
        buffer.current.push(t, [value])
      }
      elapsedRef.current = after
      setElapsed(after)
      setHeight(step === 'reach' ? Math.round(280 - 245 * after / 6) : Math.round(220 + 5 * Math.sin(after)))
      setTaps(step === 'tap' ? Math.floor(after * 3) : 0)
      if (after >= runSeconds(step)) {
        const samples: SignalPoint[] = []
        buffer.current.forEach((t, row) => samples.push({ t, value: row[0] }))
        setPhase('finished'); finish.current(samples.slice(-700))
      }
    }, 100)
    return () => clearInterval(timer)
  }, [phase, step])
  function start() { buffer.current.clear(); elapsedRef.current = 0; setElapsed(0); setTaps(0); setCountdown(COUNTDOWN_S); setPhase('countdown') }
  return { buffer, phase, elapsed, countdown, height, taps, start, pause: () => setPhase('paused'), resume: () => setPhase('running') }
}
