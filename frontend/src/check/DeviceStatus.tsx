import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { ConfettiBurst } from './ConfettiBurst'

/** `rows` overrides the per-device state with what the backend reported (sensor mode). */
export function DeviceStatus({ demo, connected, checking, detectedCount, celebrating, rows }: { demo: boolean; connected: boolean; checking: boolean; detectedCount: number; celebrating: boolean; rows?: { detected: boolean; status: string }[] }) {
  return <div className="device-status" role="status">
    <div className="device-success">
      <div className={`device-status-symbol ${connected ? 'ready' : ''} ${celebrating ? 'is-celebrating' : ''}`}><Icon name={connected ? 'check' : 'connect'} size={connected ? 42 : 34}/></div>
      {celebrating && <ConfettiBurst/>}
    </div>
    <h2>{checking ? copy.flow.connecting : connected ? copy.flow.devicesReady : copy.flow.devicesWaiting}</h2>
    <ul>{copy.flow.devices.map((device, i) => {
      const row = rows?.[i]
      const detected = row ? row.detected : connected || i < detectedCount
      const scanning = checking && (row ? false : i === detectedCount)
      return <li key={device} className={`device-row ${detected ? 'is-detected' : ''} ${scanning ? 'is-scanning' : ''}`}>
        <span className="device-row-icon"><Icon name={detected ? 'check' : i === 2 ? 'camera' : 'sensor'} size={21}/></span>
        <span className="device-row-name">{device}</span>
        <span className={`device-row-status ${detected ? 'device-ready' : 'muted'}`}>{row ? row.status : detected ? demo ? copy.flow.simulated : copy.flow.backendReady : scanning ? copy.flow.connecting : copy.flow.notConnected}</span>
      </li>
    })}</ul>
  </div>
}
