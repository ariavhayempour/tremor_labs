import { useState } from 'react'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { readCheckIn, saveLocal } from './homeStore'
export function DailyCheckIn() {
  const [values, setValues] = useState(readCheckIn)
  const [message, setMessage] = useState('')
  return <section className="home-card daily-card" aria-labelledby="daily-title"><div className="home-card-heading"><span className="home-card-icon"><Icon name="journal" size={21}/></span><div><h2 id="daily-title">{copy.home.dailyTitle}</h2><p>{copy.home.dailySubtitle}</p></div></div><form onSubmit={e => { e.preventDefault(); setMessage(saveLocal('tremor-daily-check-in', { ...values, at: new Date().toISOString() }) ? copy.home.saved : copy.home.saveError) }} onChange={() => setMessage('')}>
    <fieldset><legend>{copy.home.sleep}</legend><div className="sleep-choices">{[1,2,3,4,5].map(n => <label key={n}><input type="radio" name="sleep" value={n} checked={values.sleep === n} onChange={() => setValues({ ...values, sleep: n })}/><span>{n}</span></label>)}</div><div className="choice-hints"><span>{copy.home.poor}</span><span>{copy.home.rested}</span></div></fieldset>
    <div className="daily-second-row"><fieldset><legend>{copy.home.stress}</legend><div className="stress-choices">{copy.home.stressLevels.map((label, i) => <label key={label}><input type="radio" name="stress" value={i * 2 + 1} checked={values.stress === i * 2 + 1} onChange={() => setValues({ ...values, stress: i * 2 + 1 })}/><span>{label}</span></label>)}</div></fieldset><label className="caffeine-choice"><input type="checkbox" checked={values.caffeine} onChange={e => setValues({ ...values, caffeine: e.target.checked })}/><Icon name="coffee" size={16}/>{copy.home.caffeine}</label></div>
    <div className="daily-save"><span role="status">{message}</span><button type="submit" className="home-secondary"><Icon name="check" size={16}/>{copy.home.saveCheckIn}</button></div>
  </form></section>
}
