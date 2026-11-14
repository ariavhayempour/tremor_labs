import { useState } from 'react'
import { copy } from '../copy'
import { USE_FIXTURES, putSim } from '../api/client'
import { defaultSim, type SimParams } from '../api/types'
import { Waveform } from '../viz/Waveform'
import type { useSensorStream } from '../api/useSensorStream'
export function DevPanel({ params, onChange, stream }: { params: SimParams; onChange: (p: SimParams) => void; stream: ReturnType<typeof useSensorStream> }) {
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  async function update(next: SimParams) {
    setBusy(true)
    try { if (!USE_FIXTURES) await putSim(next); onChange(next); setMessage(copy.saved) }
    catch { setMessage(copy.error) }
    finally { setBusy(false) }
  }
  if (!import.meta.env.DEV || stream.source !== 'sim') return <p>{copy.unavailable}</p>
  const controls: { key: keyof SimParams; label: string; min: number; max: number; step: number }[] = [
    { key: 'tremor_hz', label: copy.frequency, min: 2, max: 12, step: 0.1 },
    { key: 'amplitude', label: copy.amplitude, min: 0, max: 1.5, step: 0.01 },
    { key: 'noise', label: copy.noise, min: 0, max: 0.2, step: 0.01 },
    { key: 'hand_height', label: copy.height, min: 50, max: 400, step: 1 },
  ]
  return <><span className="eyebrow">{copy.nav.dev}</span><h1>{copy.devTitle}</h1><p className="lead">{copy.devBody}</p><div className="dev-grid"><section className="panel">{controls.map(c => <label className="range-label" key={c.key}><span>{c.label}<output>{params[c.key]}</output></span><input type="range" aria-label={c.label} min={c.min} max={c.max} step={c.step} value={params[c.key]} disabled={busy} onChange={e => void update({ ...params, [c.key]: Number(e.target.value) })}/></label>)}<button className="button secondary" disabled={busy} onClick={() => void update(defaultSim)}>{copy.reset}</button><p className="muted" role="status">{message}</p></section><section className="panel"><h2>{copy.sensor}</h2><p className="muted">{copy.axis}</p><Waveform buf={stream.imu}/><p className="muted">{copy.timeAxis}</p></section></div></>
}
