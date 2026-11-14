import { useState } from 'react'
import { NavLink, Route, Routes } from 'react-router'
import { copy } from './copy'
import { Icon } from './components/Icon'
import { Home } from './screens/Home'
import { CheckIn } from './screens/CheckIn'
import { Placeholder } from './screens/Placeholder'
import { DevPanel } from './screens/DevPanel'
import { useSensorStream } from './api/useSensorStream'
import { defaultSim } from './api/types'
import { USE_FIXTURES } from './api/client'
export default function App() {
  const [params, setParams] = useState(defaultSim)
  const [menuOpen, setMenuOpen] = useState(false)
  const stream = useSensorStream(params)
  const nav = [['home', '/'], ['dashboard', '/dashboard'], ['report', '/report'], ['settings', '/settings']] as const
  return <div className="app"><button className="mobile-menu" aria-label={copy.menu} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><Icon name="menu"/></button><aside className={`sidebar ${menuOpen ? 'open' : ''}`}><NavLink to="/" className="brand" onClick={() => setMenuOpen(false)}><span className="brand-icon"><Icon name="wave" size={26}/></span>{copy.brand}<span className="brand-period">.</span></NavLink><nav>{nav.map(([key, path]) => <NavLink end={key === 'home'} to={path} key={key} onClick={() => setMenuOpen(false)}><Icon name={key}/>{copy.nav[key]}</NavLink>)}</nav><div className="sidebar-bottom">{import.meta.env.DEV && stream.source === 'sim' && <NavLink className="dev-link" to="/dev" onClick={() => setMenuOpen(false)}><Icon name="dev"/>{copy.nav.dev}</NavLink>}<div className="connection-card"><span className={`dot ${stream.connected ? '' : 'gray'}`}/><div><strong>{USE_FIXTURES ? copy.simulated : stream.connected ? copy.live : copy.disconnected}</strong><small>{stream.connected ? copy.connectedBody : copy.backendBody}</small></div></div><div className="privacy-note"><Icon name="shield" size={18}/><p>{copy.localBody}</p></div></div></aside><main><Routes><Route path="/" element={<Home stream={stream}/>}/><Route path="/check-in" element={<CheckIn/>}/><Route path="/dev" element={<DevPanel params={params} onChange={setParams} stream={stream}/>}/>{[['/dashboard', copy.nav.dashboard], ['/report', copy.nav.report], ['/settings', copy.nav.settings], ['/check/:checkId', copy.previewTitle], ['/results/:checkId', copy.activity]].map(([path, title]) => <Route key={path} path={path} element={<Placeholder title={title}/>}/>)}<Route path="*" element={<Placeholder title={copy.notFound}/>}/></Routes><footer><Icon name="shield" size={16}/>{copy.footer}</footer></main></div>
}
