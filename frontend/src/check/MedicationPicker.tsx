import { copy } from '../copy'
import type { CheckInRequest } from '../api/types'
const t = copy.sensorCheck
const doseChoices: { label: string; body: CheckInRequest }[] = [
  { label: t.doseNow, body: { medication: 'now' } },
  { label: t.dose30, body: { medication: 'hours_ago', hours_ago: 0.5 } },
  { label: t.dose1, body: { medication: 'hours_ago', hours_ago: 1 } },
  { label: t.dose2, body: { medication: 'hours_ago', hours_ago: 2 } },
  { label: t.dose3, body: { medication: 'hours_ago', hours_ago: 3 } },
  { label: t.dose4, body: { medication: 'hours_ago', hours_ago: 4 } },
  { label: t.notYet, body: { medication: 'not_yet' } },
]
export function MedicationPicker({ busy, onPick }: { busy: boolean; onPick: (body: CheckInRequest) => void }) {
  return <fieldset className="medication-picker" disabled={busy}>
    <legend>{t.checkIn}</legend>
    <p className="muted">{t.checkInHelp}</p>
    <div className="medication-choices">{doseChoices.map(choice => <button type="button" key={choice.label} onClick={() => onPick(choice.body)}>{choice.label}</button>)}</div>
    {busy && <p role="status">{t.creating}</p>}
  </fieldset>
}
