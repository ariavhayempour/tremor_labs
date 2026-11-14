import { copy } from '../copy'
import type { SimParams } from '../api/types'
import { SimulatorControls } from '../components/SimulatorControls'
import { Waveform } from '../viz/Waveform'
import type { useSensorStream } from '../api/useSensorStream'
export function DevPanel({ params, onChange, stream }: { params: SimParams; onChange: (p: SimParams) => void; stream: ReturnType<typeof useSensorStream> }) {
  if (!import.meta.env.DEV || stream.source !== 'sim') return <p>{copy.unavailable}</p>
  return <><span className="eyebrow">{copy.nav.dev}</span><h1>{copy.devTitle}</h1><p className="lead">{copy.devBody}</p><div className="dev-grid"><section className="panel"><SimulatorControls params={params} onChange={onChange}/></section><section className="panel"><h2>{copy.sensor}</h2><p className="muted">{copy.axis}</p><Waveform buf={stream.imu}/><p className="muted">{copy.timeAxis}</p></section></div></>
}
