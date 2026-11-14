import { useState } from 'react'
import { Link } from 'react-router'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { availableStep, readSession, steps, storageKey } from '../check/checkSession'
import { ActivityChart } from '../home/ActivityChart'
import { HandComparison } from '../home/HandComparison'
import { dateLabel, readHistory } from '../home/homeStore'
export function Home() {
  const [history] = useState(readHistory)
  const [session] = useState(readSession)
  const stage = availableStep(session)
  const resume = stage > 0 && stage < 5
  const next = resume ? steps[stage] : 'connect'
  function prepareCheck() { if (stage === 5) { sessionStorage.removeItem(storageKey); sessionStorage.removeItem('tremor-history-recorded') } }
  return <div className="home-grid">
    <section className="home-card operate-card" aria-labelledby="movement-title">
      <div className="home-card-heading"><span className="home-card-icon"><Icon name="wave" size={23}/></span><span className="home-ready"><span/>{copy.home.ready}</span></div>
      <div className="operate-title"><span className="home-eyebrow">{copy.home.yourRoutine}</span><h1 id="movement-title">{copy.home.testTitle}</h1><p>{copy.home.testSubtitle}</p></div>
      <div className="home-test-meta"><span><Icon name="clock" size={16}/>{copy.duration}</span><span><Icon name="tap" size={16}/>{copy.home.bothHands}</span></div>
      <ol className="home-test-steps">{steps.map((step, i) => <li key={step}><span className={`home-step-icon ${i < stage ? 'complete' : ''}`}><Icon name={i < stage ? 'check' : ['connect','rest','posture','reach','tap'][i]} size={20}/></span><div><strong>{copy.flow.steps[step].label}</strong><span>{copy.home.stepDetails[i]}</span></div><span className="home-step-index">{String(i + 1).padStart(2, '0')}</span></li>)}</ol>
      <div className="operate-bottom"><div className="home-preparation"><Icon name="sensor" size={17}/><span>{resume ? `${stage} ${copy.home.stepsComplete}` : copy.home.prepare}</span></div><Link className="home-primary" to={`/check/${next}`} onClick={prepareCheck}>{resume ? copy.home.resume : copy.home.start}<Icon name="arrow" size={20}/></Link></div>
    </section>
    <section className="home-card trends-card" aria-labelledby="trends-title"><div className="home-card-heading"><span className="home-card-icon"><Icon name="dashboard" size={21}/></span><div><h2 id="trends-title">{copy.home.trends}</h2><p>{copy.home.trendsSubtitle}</p></div><span className="sample-badge">{copy.home.sampleHistory}</span></div><div className="home-history-numbers"><strong>{history.length}<span>{copy.home.checks}</span></strong><span>{copy.home.last14Days}<small>{copy.home.latest} {dateLabel(history[0].at)}</small></span></div><ActivityChart history={history}/><div className="home-trend-footer"><span>{copy.home.last7Days}</span><Link to="/dashboard" className="home-text-link">{copy.home.openHistory}<Icon name="arrow" size={17}/></Link></div></section>
    <HandComparison/>
  </div>
}
