import { useEffect, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router'
import { copy } from './copy'
import { Icon } from './components/Icon'
import { Home } from './screens/Home'
import { HomeShell } from './home/HomeShell'
import { History } from './screens/History'
import { CheckFlow } from './check/CheckFlow'
import { Placeholder } from './screens/Placeholder'
import { DevPanel } from './screens/DevPanel'
import { useSensorStream } from './api/useSensorStream'
import { defaultSim } from './api/types'
import { USE_FIXTURES, getSim } from './api/client'
import { Results } from './results/Results'
import { Report } from './report/Report'
import { Settings } from './settings/Settings'
import { usePageTransition } from './hooks/usePageTransition'
export default function App() {
  const [params, setParams] = useState(defaultSim)
  const [menuOpen, setMenuOpen] = useState(false)
  const stream = useSensorStream(params)
  // The simulator keeps its own parameters; mirror them so the dev panel starts in sync.
  useEffect(() => { if (!USE_FIXTURES && stream.source === 'sim') void getSim().then(setParams, () => undefined) }, [stream.source])
  const { pathname } = useLocation()
  usePageTransition(pathname)
  if (pathname === '/check-in') return <Navigate to="/check/connect" replace/>
  if (pathname.startsWith('/check/')) return <Routes><Route path="/check/:step" element={<CheckFlow stream={stream}/>}/></Routes>
  if (pathname === '/' || pathname === '/overview') return <HomeShell><Home/></HomeShell>
  if (pathname === '/dashboard') return <HomeShell dashboard><History/></HomeShell>
  const nav = [['home', '/overview'], ['dashboard', '/dashboard'], ['report', '/report'], ['settings', '/settings']] as const
  return (
    <div className="app">
      <header className={`topbar ${menuOpen ? 'open' : ''}`}>
        <NavLink to="/overview" className="brand" onClick={() => setMenuOpen(false)}>
          <span className="brand-icon"><Icon name="wave" size={21}/></span>
          {copy.brand}<span className="brand-period">.</span>
        </NavLink>
        <button className="mobile-menu" aria-label={copy.menu} aria-controls="main-navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>
          <Icon name={menuOpen ? 'close' : 'menu'}/>
        </button>
        <nav id="main-navigation">
          {nav.map(([key, path]) => (
            <NavLink end={key === 'home'} to={path} key={key} onClick={() => setMenuOpen(false)}>
              <Icon name={key}/>{copy.nav[key]}
            </NavLink>
          ))}
          {import.meta.env.DEV && stream.source === 'sim' && (
            <NavLink to="/dev" onClick={() => setMenuOpen(false)}><Icon name="dev"/>{copy.nav.dev}</NavLink>
          )}
        </nav>
        <div className="connection-card">
          <span className={`dot ${stream.connected ? '' : 'gray'}`}/>
          <div>
            <strong>{USE_FIXTURES ? copy.simulated : stream.connected ? copy.live : copy.disconnected}</strong>
            
          </div>
        </div>
      </header>
      <main><Routes><Route path="/dev" element={<DevPanel params={params} onChange={setParams} stream={stream}/>}/><Route path="/results/:checkId" element={<Results/>}/>{!USE_FIXTURES && <><Route path="/report" element={<Report/>}/><Route path="/settings" element={<Settings/>}/></>}{(USE_FIXTURES ? [['/dashboard', copy.nav.dashboard], ['/report', copy.nav.report], ['/settings', copy.nav.settings]] : [['/dashboard', copy.nav.dashboard]]).map(([path, title]) => <Route key={path} path={path} element={<Placeholder title={title}/>}/>)}<Route path="*" element={<Placeholder title={copy.notFound}/>}/></Routes><footer><Icon name="shield" size={16}/>{copy.footer}</footer></main>
    </div>
  )
}
