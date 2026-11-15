import { useEffect, useRef, type RefObject } from 'react'
import { copy } from '../copy'
import { RingBuf } from './ringbuf'
export function Waveform({ buf, paused = false, min = -2, max = 2, seconds = 5, label = copy.signalLabel, center = false }: { buf: RefObject<RingBuf>; paused?: boolean; min?: number; max?: number; seconds?: number; label?: string; center?: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const snapshot = new RingBuf(buf.current.capacity, buf.current.width)
    if (paused) buf.current.forEach((t, row) => snapshot.push(t, row))
    const data = paused ? snapshot : buf.current
    let frame: number
    function draw() {
      const el = canvas.current
      if (!el) return
      const ctx = el.getContext('2d')
      if (!ctx) return
      const { width, height } = el.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      if (el.width !== Math.round(width * dpr) || el.height !== Math.round(height * dpr)) { el.width = Math.round(width * dpr); el.height = Math.round(height * dpr) }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, width, height)
      const left = 48, plot = width - left - 8
      ctx.font = '12px system-ui'
      const palette = getComputedStyle(el)
      ctx.fillStyle = palette.getPropertyValue('--chart-label').trim()
      ctx.strokeStyle = palette.getPropertyValue('--chart-grid').trim()
      for (let i = 0; i < 5; i++) {
        const y = 12 + i * (height - 36) / 4
        ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width, y); ctx.stroke()
        ctx.fillText((max - i * (max - min) / 4).toFixed(max > 10 ? 0 : 1), 9, y + 4)
      }
      for (let i = 0; i <= seconds; i++) ctx.fillText(String(i - seconds), left + i * plot / seconds - 4, height - 2)
      const latest = data.last()?.t ?? 0
      // Centering removes the gravity offset so a real sensor's axis stays on screen.
      let offset = 0
      if (center) {
        let sum = 0, n = 0
        data.forEach((t, row) => { if (t >= latest - seconds) { sum += row[0]; n++ } })
        offset = n ? sum / n : 0
      }
      ctx.strokeStyle = palette.getPropertyValue('--signal').trim(); ctx.lineWidth = 1.7; ctx.beginPath()
      let first = true
      data.forEach((t, row) => {
        if (t < latest - seconds) return
        const x = left + (t - latest + seconds) / seconds * plot
        const y = 12 + (max - Math.max(min, Math.min(max, row[0] - offset))) / (max - min) * (height - 36)
        if (first) { ctx.moveTo(x, y); first = false } else ctx.lineTo(x, y)
      })
      ctx.stroke()
      frame = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(frame)
  }, [buf, paused, min, max, seconds, center])
  return <canvas ref={canvas} role="img" aria-label={label} />
}
