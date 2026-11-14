import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { ConfettiBurst } from './ConfettiBurst'

export function DeviceStatus({ demo, connected, checking, detectedCount, celebrating }: { demo: boolean; connected: boolean; checking: boolean; detectedCount: number; celebrating: boolean }) {
  return <div className="device-status" role="status">
    <div className="device-success">
      <div className={`device-status-symbol ${connected ? 'ready' : ''} ${celebrating ? 'is-celebrating' : ''}`}><Icon name={connected ? 'check' : 'connect'} size={connected ? 42 : 34}/></div>
      {celebrating && <ConfettiBurst/>}
    </div>
    <h2>{checking ? copy.flow.connecting : connected ? copy.flow.devicesReady : copy.flow.devicesWaiting}</h2>
    <ul>{copy.flow.devices.map((device, i) => {
      const detected = connected || i < detectedCount
      const scanning = checking && i === detectedCount
      return <li key={device} className={`device-row ${detected ? 'is-detected' : ''} ${scanning ? 'is-scanning' : ''}`}>
        <span className="device-row-icon"><Icon name={detected ? 'check' : i === 2 ? 'camera' : 'sensor'} size={21}/></span>
        <span className="device-row-name">{device}</span>
        <span className={`device-row-status ${detected ? 'device-ready' : 'muted'}`}>{detected ? demo ? copy.flow.simulated : copy.flow.backendReady : scanning ? copy.flow.connecting : copy.flow.notConnected}</span>
      </li>
    })}</ul>
  </div>
}
