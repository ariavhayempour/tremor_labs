import { lazy, Suspense, useEffect, useState } from 'react'
import { getReport } from '../api/client'
import type { ReportOut } from '../api/types'
import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { dayLabel } from '../dashboard/format'
import { dateLabel } from '../home/homeStore'
const DoseCurvePlot = lazy(() => import('../dashboard/DoseCurvePlot'))
const r = copy.report, d = copy.dashboard
const fmt = (v: number | null, n: number) => v === null ? `— · n=${n}` : `${v.toFixed(v >= 10 ? 0 : 1)} · n=${n}`
const DAYS = 14

/** One printable page for a clinic visit; every insight carries its sample count. */
export function Report() {
  const [state, setState] = useState<ReportOut | 'error' | null>(null)
  useEffect(() => {
    let alive = true
    getReport(DAYS).then(rep => { if (alive) setState(rep) }, () => { if (alive) setState('error') })
    return () => { alive = false }
  }, [])
  if (state === null || state === 'error') return <section className="panel"><h1>{r.title}</h1><p role={state ? 'alert' : 'status'}>{state ? r.error : r.loading}</p></section>
  const rep = state
  const binN = rep.dose_response.reduce((n, b) => n + b.count, 0)
  return <article className="report-page">
    <header className="report-header">
      <div><h1>{r.title}</h1><p className="muted">{r.subtitle}</p></div>
      <button className="button primary no-print" onClick={() => window.print()}><Icon name="report" size={18}/>{r.print}</button>
    </header>
    <dl className="report-meta">
      <div><dt>{r.period}</dt><dd>{dateLabel(rep.period.start)} – {dateLabel(rep.period.end)}</dd></div>
      <div><dt>{r.checks}</dt><dd>{rep.checks_completed}</dd></div>
      <div><dt>{r.generated}</dt><dd>{new Date(rep.generated_at).toLocaleString()}</dd></div>
    </dl>
    <section className="report-section">
      <h2>{d.wearingOff}</h2>
      <p>{rep.returns_after_h === null ? d.returnsUnknown : `${d.returnsAfter} ${rep.returns_after_h} ${d.returnsAfterUnit} (n=${binN}).`}</p>
      {rep.dose_response.length > 0 && <Suspense fallback={<div className="home-chart" aria-busy="true"/>}><DoseCurvePlot bins={rep.dose_response} returnsAfter={rep.returns_after_h}/></Suspense>}
    </section>
    <section className="report-section">
      <h2>{d.profile}</h2><p className="muted">{d.profileSubtitle}</p>
      <table><thead><tr><th>{d.test}</th><th>{d.firstWeek}</th><th>{d.current}</th></tr></thead>
        <tbody>{rep.profile.map(p => <tr key={p.test_type}><td>{copy.results.tests[p.test_type]}</td><td>{fmt(p.first_week, p.first_n)}</td><td>{fmt(p.current, p.current_n)}</td></tr>)}</tbody></table>
    </section>
    <section className="report-section">
      <h2>{r.daily}</h2>
      <table><thead><tr><th>{r.date}</th><th>{r.meanRest}</th><th>{r.count}</th></tr></thead>
        <tbody>{rep.daily.map(p => <tr key={p.date}><td>{dayLabel(p.date)}</td><td>{p.mean_rest === null ? '—' : p.mean_rest.toFixed(3)}</td><td>{p.count}</td></tr>)}</tbody></table>
    </section>
    <p className="muted">{r.about}</p>
  </article>
}
