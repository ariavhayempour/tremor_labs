import { useEffect, useState } from 'react'
import { getSettings, putSettings } from '../api/client'
import type { SettingsModel } from '../api/types'
import { copy } from '../copy'
import { parseBand, parseTimes } from './parse'
const s = copy.settings

/** Backend settings: dose and reminder times and an optional fixed posture band. The hand is chosen per check. */
export function Settings() {
  const [loaded, setLoaded] = useState<SettingsModel | null>(null)
  const [doses, setDoses] = useState('')
  const [reminders, setReminders] = useState('')
  const [auto, setAuto] = useState(true)
  const [low, setLow] = useState('170')
  const [high, setHigh] = useState('230')
  const [message, setMessage] = useState('')
  function apply(m: SettingsModel) {
    setLoaded(m); setDoses(m.dose_times.join(', ')); setReminders(m.reminder_times.join(', '))
    setAuto(m.posture_band === null)
    if (m.posture_band) { setLow(String(m.posture_band[0])); setHigh(String(m.posture_band[1])) }
  }
  useEffect(() => {
    let alive = true
    getSettings().then(m => { if (alive) apply(m) }, () => { if (alive) setMessage(s.error) })
    return () => { alive = false }
  }, [])
  async function save() {
    const dose_times = parseTimes(doses), reminder_times = parseTimes(reminders)
    const band = auto ? null : parseBand(low, high)
    if (!dose_times || !reminder_times || (!auto && !band)) { setMessage(s.invalid); return }
    try { apply(await putSettings({ dose_times, reminder_times, posture_band: band })); setMessage(s.saved) }
    catch { setMessage(s.error) }
  }
  if (!loaded) return <section className="panel"><h1>{s.title}</h1><p role="status">{message || s.loading}</p></section>
  return <section className="settings-page">
    <h1>{s.title}</h1>
    <form className="panel settings-form" onSubmit={e => { e.preventDefault(); void save() }} onChange={() => setMessage('')}>
      <label>{s.doseTimes}<input value={doses} onChange={e => setDoses(e.target.value)} aria-describedby="times-help"/></label>
      <label>{s.reminderTimes}<input value={reminders} onChange={e => setReminders(e.target.value)} aria-describedby="times-help"/></label>
      <p id="times-help" className="muted">{s.timesHelp}</p>
      <fieldset><legend>{s.band}</legend>
        <label className="checkbox-row"><input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)}/>{s.bandAuto}</label>
        {!auto && <div className="band-inputs"><label>{s.low}<input type="number" min={0} max={2000} value={low} onChange={e => setLow(e.target.value)}/></label><label>{s.high}<input type="number" min={0} max={2000} value={high} onChange={e => setHigh(e.target.value)}/></label></div>}
      </fieldset>
      <button className="button primary" type="submit">{s.save}</button>
      <p role="status">{message}</p>
    </form>
  </section>
}
