import { useState } from 'react'
import { Icon } from './Icon'
import { copy } from '../copy'
import { USE_FIXTURES, putSim } from '../api/client'
import { defaultSim, type SimParams } from '../api/types'
export function SimulatorControls({ params, onChange }: { params: SimParams; onChange: (p: SimParams) => void }) {
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  async function update(next: SimParams) {
    setBusy(true)
    try { if (!USE_FIXTURES) await putSim(next); onChange(next); setMessage(copy.saved) }
    catch { setMessage(copy.error) }
    finally { setBusy(false) }
  }
  const controls: { key: keyof SimParams; label: string; min: number; max: number; step: number }[] = [
    { key: 'tremor_hz', label: copy.frequency, min: 2, max: 12, step: 0.1 },
    { key: 'amplitude', label: copy.amplitude, min: 0, max: 1.5, step: 0.01 },
    { key: 'noise', label: copy.noise, min: 0, max: 0.2, step: 0.01 },
    { key: 'hand_height', label: copy.height, min: 50, max: 400, step: 1 },
  ]
  return <>{controls.map(c => <label className="range-label" key={c.key}><span>{c.label}<output>{params[c.key]}</output></span><input type="range" aria-label={c.label} min={c.min} max={c.max} step={c.step} value={params[c.key]} disabled={busy} onChange={e => void update({ ...params, [c.key]: Number(e.target.value) })}/></label>)}<button className="icon-button" aria-label={copy.reset} data-tooltip={copy.reset} disabled={busy} onClick={() => void update(defaultSim)}><Icon name="reset" size={20}/></button><p className="muted control-message" role="status">{message}</p></>
}
