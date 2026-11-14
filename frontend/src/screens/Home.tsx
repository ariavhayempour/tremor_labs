import { useState } from 'react'
import { Link } from 'react-router'
import type { SimParams } from '../api/types'
import type { useSensorStream } from '../api/useSensorStream'
import { USE_FIXTURES } from '../api/client'
import { SimulatorControls } from '../components/SimulatorControls'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { Waveform } from '../viz/Waveform'

export function Home({ stream, params, onChange }: { stream: ReturnType<typeof useSensorStream>; params: SimParams; onChange: (p: SimParams) => void }) {
  const [paused, setPaused] = useState(false)
  return <>
    <div className="page-heading">
      <h1>{copy.nav.home}</h1>
      <span className="privacy"><Icon name="shield" size={18}/>{copy.local}</span>
    </div>
    <div className="overview-workspace">
      <div className="overview-input">
        <section className="input-section" aria-labelledby="input-heading">
          <div className="section-heading"><h2 id="input-heading">{copy.input}</h2><Icon name="settings" size={20}/></div>
          {import.meta.env.DEV && stream.source === 'sim'
            ? <><h3 className="subheading">{copy.controls}</h3><SimulatorControls params={params} onChange={onChange}/></>
            : <p className="connection-message" role="status">{stream.connected ? copy.backendBody : copy.offline}</p>}
        </section>
        <section className="check-section" aria-labelledby="check-heading">
          <div className="section-heading"><h2 id="check-heading">{copy.check}</h2><span className="duration"><Icon name="clock" size={16}/>{copy.duration}</span></div>
          <ol className="check-list">
            {copy.steps.map(step => <li key={step.name}><Icon name={step.icon} size={20}/><span>{step.name}</span><span className="muted">{step.time}</span></li>)}
          </ol>
          <Link className="button primary" to="/check-in">{copy.start}<Icon name="arrow" size={20}/></Link>
        </section>
      </div>
      <div className="overview-output">
        <section className="signal-tool" aria-labelledby="signal-heading">
          <div className="section-heading">
            <h2 id="signal-heading">{copy.sensor}</h2>
            <span className={`status ${stream.connected ? '' : 'offline'}`}><span className="dot"/>{USE_FIXTURES ? copy.simulated : stream.connected ? copy.live : copy.disconnected}</span>
          </div>
          <div className="signal-toolbar">
            <span><Icon name="wave" size={18}/>{copy.signal}</span>
            <div className="signal-actions">
              {paused && <span className="muted">{copy.paused}</span>}
              <button className="icon-button" aria-label={paused ? copy.resume : copy.pause} data-tooltip={paused ? copy.resume : copy.pause} onClick={() => setPaused(!paused)}><Icon name={paused ? 'play' : 'pause'} size={20}/></button>
            </div>
          </div>
          <div className="waveform-frame">
            <div className="chart-label">{copy.axis}</div>
            <Waveform buf={stream.imu} paused={paused}/>
            <div className="chart-bottom"><span>{copy.sample}</span><span>{copy.timeAxis}</span></div>
          </div>
          <div className="signal-footer" role="status">{USE_FIXTURES ? copy.fixtureNotice : !stream.connected ? copy.offline : copy.backendBody}</div>
        </section>
        <section className="activity" aria-labelledby="activity-heading">
          <h2 id="activity-heading">{copy.activity}</h2>
          <div className="empty-row"><Icon name="report" size={24}/><span>{copy.noChecks}</span></div>
        </section>
      </div>
    </div>
  </>
}
