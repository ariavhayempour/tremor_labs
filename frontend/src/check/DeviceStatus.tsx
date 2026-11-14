import { copy } from '../copy'
import { Icon } from '../components/Icon'
export function DeviceStatus({ demo, connected, checking }: { demo: boolean; connected: boolean; checking: boolean }) {
  return <div className="device-status" role="status">
    <div className={`device-status-symbol ${connected ? 'ready' : ''}`}><Icon name={connected ? 'check' : 'connect'} size={34}/></div>
    <h2>{checking ? copy.flow.connecting : connected ? copy.flow.devicesReady : copy.flow.devicesWaiting}</h2>
    <ul>{copy.flow.devices.map((device, i) => <li key={device}><Icon name={i === 2 ? 'camera' : 'sensor'} size={21}/><span>{device}</span><span className={connected ? 'device-ready' : 'muted'}>{connected ? demo ? copy.flow.simulated : copy.flow.backendReady : copy.flow.notConnected}</span></li>)}</ul>
  </div>
}
