import { lazy, Suspense, useState } from 'react'
import { Link } from 'react-router'
import { Icon } from '../components/Icon'
import { SegmentedControl } from '../components/SegmentedControl'
import { copy } from '../copy'
import { ActivityChart } from '../home/ActivityChart'
import { dateLabel, timeLabel } from '../home/homeStore'
import { sinceDose } from '../results/format'
import { dailyBars, testsDone } from './format'
import { useDashboard } from './useDashboard'
const DoseCurvePlot = lazy(() => import('./DoseCurvePlot'))
const d = copy.dashboard, h = copy.home
const fmt = (v: number | null, n: number) => v === null ? '—' : `${v.toFixed(v >= 10 ? 0 : 1)} · n=${n}`

/** The dashboard on backend insights: activity, wearing-off curve, movement profile, recent checks. */
export function LiveHistory() {
  const [days, setDays] = useState(14)
  const state = useDashboard(days)
  const heading = <div className="history-heading"><div><Link className="home-text-link" to="/"><Icon name="back" size={16}/>{h.home}</Link><h1>{h.historyTitle}</h1></div><SegmentedControl<number> className="history-period" label={h.period} value={days} onChange={setDays} options={[{ value: 7, label: `7 ${h.days}` }, { value: 14, label: `14 ${h.days}` }]}/></div>
  if (state.status !== 'ready') return <div className="history-page">{heading}<section className="home-card"><p role={state.status === 'error' ? 'alert' : 'status'}>{state.status === 'error' ? d.error : d.loading}</p></section></div>
  const { summary, dose, profile, checks } = state.data
  return <div className="history-page">
    {heading}
    <section className="home-card history-chart-card">
      <div className="home-history-numbers"><strong>{summary.checks_completed}<span>{d.checksCompleted}</span></strong><strong>{summary.streak_days}<span>{d.streak}</span></strong></div>
      <ActivityChart data={dailyBars(summary.daily)} days={days}/>
    </section>
    <section className="home-card" aria-labelledby="wearing-off-title">
      <h2 id="wearing-off-title">{d.wearingOff}</h2><p className="muted">{d.wearingOffSubtitle}</p>
      <p className="returns-after">{dose.returns_after_h === null ? d.returnsUnknown : `${d.returnsAfter} ${dose.returns_after_h} ${d.returnsAfterUnit}.`}</p>
      {dose.bins.length ? <Suspense fallback={<div className="home-chart" aria-busy="true"/>}><DoseCurvePlot bins={dose.bins} returnsAfter={dose.returns_after_h}/></Suspense> : <p>{d.empty}</p>}
    </section>
    <section className="home-card history-list" aria-labelledby="profile-title">
      <h2 id="profile-title">{d.profile}</h2><p className="muted">{d.profileSubtitle}</p>
      <table><thead><tr><th>{d.test}</th><th>{d.firstWeek}</th><th>{d.current}</th></tr></thead>
        <tbody>{profile.map(p => <tr key={p.test_type}><td>{copy.results.tests[p.test_type]}</td><td>{fmt(p.first_week, p.first_n)}</td><td>{fmt(p.current, p.current_n)}</td></tr>)}</tbody></table>
    </section>
    <section className="home-card history-list" aria-labelledby="recent-title">
      <h2 id="recent-title">{h.recentChecks}</h2>
      {checks.length ? <table><thead><tr><th>{h.date}</th><th>{h.time}</th><th>{d.sinceDose}</th><th>{d.tests}</th></tr></thead>
        <tbody>{checks.map(c => <tr key={c.id}><td><Link to={`/results/${c.id}`}>{dateLabel(c.created_at)}</Link></td><td>{timeLabel(c.created_at)}</td><td>{c.minutes_since_dose === null ? d.noDose : sinceDose(c.minutes_since_dose).replace(` ${copy.results.sinceDose}`, '')}</td><td>{testsDone(c)} {d.of4}</td></tr>)}</tbody></table>
        : <p>{d.empty}</p>}
    </section>
  </div>
}
