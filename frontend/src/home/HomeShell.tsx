import './home.css'
import { useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { HomeDialog } from './HomeDialog'
import { readProfile } from './homeStore'
export function HomeShell({ children, dashboard = false }: { children: ReactNode; dashboard?: boolean }) {
  const [dialog, setDialog] = useState<'settings' | 'login' | null>(null)
  const [profile, setProfile] = useState(readProfile)
  return <div className={`home-app ${dashboard ? 'history-app' : ''}`}><header className="home-header"><Link className="home-brand" to="/"><span><Icon name="wave" size={23}/></span>{copy.flow.brand}</Link><nav aria-label={copy.home.navigation}><NavLink to="/" end className={({ isActive }) => isActive || !dashboard ? 'active' : ''}><Icon name="home" size={17}/>{copy.home.home}</NavLink><NavLink to="/dashboard"><Icon name="dashboard" size={17}/>{copy.home.trends}</NavLink></nav><div className="home-header-actions"><span className="home-demo">{copy.home.demoWorkspace}</span><button aria-label={copy.home.settings} className="home-toolbar-button" onClick={() => setDialog('settings')}><Icon name="settings" size={18}/><span>{copy.home.settings}</span></button><button className="home-login" onClick={() => setDialog('login')}><Icon name="user" size={17}/><span>{profile.name || copy.home.login}</span></button></div></header><main className="home-main">{children}</main><footer className="home-footer">{copy.footer}</footer>{dialog && <HomeDialog kind={dialog} onClose={() => setDialog(null)} onSaved={() => setProfile(readProfile())}/>}</div>
}
