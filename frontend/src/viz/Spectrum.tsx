import { useEffect, useRef, type RefObject } from 'react'
import { copy } from '../copy'
import type { SpectrumMsg } from '../api/types'
const MAX_HZ = 15

/** Live power spectrum (Hz on x, linear PSD on y) with the detected peak marked. */
export function Spectrum({ spectrum, label = copy.spectrum.label }: { spectrum: RefObject<SpectrumMsg | null>; label?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    let frame: number
    function draw() {
      const el = canvas.current
      const ctx = el?.getContext('2d')
      if (!el || !ctx) return
      const { width, height } = el.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      if (el.width !== Math.round(width * dpr) || el.height !== Math.round(height * dpr)) { el.width = Math.round(width * dpr); el.height = Math.round(height * dpr) }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, width, height)
      const palette = getComputedStyle(el)
      const left = 12, bottom = height - 18, plot = width - left - 8
      const x = (hz: number) => left + hz / MAX_HZ * plot
      ctx.font = '12px system-ui'
      ctx.fillStyle = palette.getPropertyValue('--chart-label').trim()
      for (let hz = 0; hz <= MAX_HZ; hz += 3) ctx.fillText(String(hz), x(hz) - 4, height - 2)
      const s = spectrum.current
      if (s && s.psd.length) {
        const top = Math.max(...s.psd.filter((_, i) => s.freqs[i] <= MAX_HZ)) || 1
        ctx.strokeStyle = palette.getPropertyValue('--signal').trim(); ctx.lineWidth = 1.7; ctx.beginPath()
        s.freqs.forEach((hz, i) => {
          if (hz > MAX_HZ) return
          const y = bottom - s.psd[i] / top * (bottom - 24)
          if (i === 0) ctx.moveTo(x(hz), y); else ctx.lineTo(x(hz), y)
        })
        ctx.stroke()
        ctx.font = '600 14px system-ui'
        if (s.peak_hz !== null) {
          ctx.strokeStyle = palette.getPropertyValue('--chart-grid').trim(); ctx.setLineDash([4, 4])
          ctx.beginPath(); ctx.moveTo(x(s.peak_hz), 20); ctx.lineTo(x(s.peak_hz), bottom); ctx.stroke(); ctx.setLineDash([])
          ctx.fillText(`${copy.spectrum.peak} ${s.peak_hz.toFixed(1)} Hz`, Math.min(x(s.peak_hz) + 6, width - 110), 16)
        } else ctx.fillText(copy.spectrum.noPeak, left, 16)
      } else ctx.fillText(copy.spectrum.waiting, left, 16)
      frame = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(frame)
  }, [spectrum])
  return <canvas ref={canvas} role="img" aria-label={label}/>
}
