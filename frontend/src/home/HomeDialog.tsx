import { useEffect, useRef, useState } from 'react'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { readPreferences, readProfile, saveLocal } from './homeStore'
export function HomeDialog({ kind, onClose, onSaved }: { kind: 'login' | 'settings'; onClose: () => void; onSaved: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [profile, setProfile] = useState(readProfile)
  const [preferences, setPreferences] = useState(readPreferences)
  const [message, setMessage] = useState('')
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close() }, [])
  return <dialog className="home-dialog" ref={dialog} onClose={() => { if (!dialog.current?.open) onClose() }} aria-labelledby="dialog-title"><div className="home-dialog-heading"><h2 id="dialog-title">{kind === 'settings' ? copy.home.settings : copy.home.loginTitle}</h2><button type="button" className="home-icon-button" aria-label={copy.home.close} onClick={onClose}><Icon name="close" size={20}/></button></div><form onSubmit={e => { e.preventDefault(); const saved = saveLocal(kind === 'login' ? 'tremor-profile' : 'tremor-preferences', kind === 'login' ? profile : preferences); if (saved) { onSaved(); onClose() } else setMessage(copy.home.saveError) }}>
    {kind === 'login' ? <><p className="dialog-note">{copy.home.loginNote}</p><label>{copy.home.name}<input required autoComplete="name" value={profile.name} onChange={e => setProfile({ ...profile, name: e.target.value })}/></label><label>{copy.home.email}<input required type="email" autoComplete="email" value={profile.email} onChange={e => setProfile({ ...profile, email: e.target.value })}/></label></> : <><label>{copy.home.testHand}<select value={preferences.hand} onChange={e => setPreferences({ ...preferences, hand: e.target.value })}><option value="right">{copy.flow.rightHand}</option><option value="left">{copy.flow.leftHand}</option></select></label><label className="checkbox-row"><input type="checkbox" checked={preferences.reminders} onChange={e => setPreferences({ ...preferences, reminders: e.target.checked })}/>{copy.home.reminders}</label><p className="dialog-note">{copy.home.settingsNote}</p></>}
    <p role="status">{message}</p><button className="home-primary" type="submit">{kind === 'login' ? copy.home.continue : copy.home.saveSettings}<Icon name="arrow" size={18}/></button>
  </form></dialog>
}
