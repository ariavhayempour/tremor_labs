import { useEffect, useRef, type RefObject } from 'react'
import { copy } from '../copy'
import type { RingBuf } from './ringbuf'
export function Waveform({ buf }: { buf: RefObject<RingBuf> }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
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
      ctx.fillStyle = '#71837c'
      ctx.strokeStyle = '#e5ece7'
      for (let i = 0; i < 5; i++) {
        const y = 12 + i * (height - 36) / 4
        ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width, y); ctx.stroke()
        ctx.fillText((2 - i).toFixed(1), 9, y + 4)
      }
      for (let i = 0; i <= 5; i++) ctx.fillText(String(i - 5), left + i * plot / 5 - 4, height - 2)
      const latest = buf.current.last()?.t ?? 0
      ctx.strokeStyle = '#377968'; ctx.lineWidth = 1.7; ctx.beginPath()
      let first = true
      buf.current.forEach((t, row) => {
        if (t < latest - 5) return
        const x = left + (t - latest + 5) / 5 * plot
        const y = 12 + (2 - Math.max(-2, Math.min(2, row[0]))) / 4 * (height - 36)
        if (first) { ctx.moveTo(x, y); first = false } else ctx.lineTo(x, y)
      })
      ctx.stroke()
      frame = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(frame)
  }, [buf])
  return <canvas ref={canvas} role="img" aria-label={copy.signalLabel} />
}
