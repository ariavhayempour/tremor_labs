import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError, getCheck, led } from '../api/client'
import type { CheckSummaryOut, Hand } from '../api/types'
import { Icon } from '../components/Icon'
import { freshSession, otherHand, storageKey } from '../check/checkSession'
import { copy } from '../copy'
import './results.css'
import { cardBaseline, cardValue, sinceDose } from './format'
const r = copy.results

export function Results() {
  const { checkId } = useParams()
  const id = Number(checkId)
  const [data, setData] = useState<CheckSummaryOut | null>(null)
  const [loadError, setError] = useState('')
  const valid = Number.isInteger(id)
  const error = valid ? loadError : r.missing
  useEffect(() => {
    if (!valid) return
    let alive = true
    getCheck(id).then(d => { if (alive) setData(d) }, e => { if (alive) setError(e instanceof ApiError && e.status === 404 ? r.missing : r.error) })
    led('idle')
    return () => { alive = false }
  }, [id, valid])
  // The next check starts on the connect step with the hand preselected.
  function newCheck(hand?: Hand) { try { if (hand) sessionStorage.setItem(storageKey, JSON.stringify(freshSession('sensor', hand))); else sessionStorage.removeItem(storageKey) } catch { /* Storage may be disabled. */ } }
  if (error) return <section className="results-page"><h1>{r.title}</h1><p role="alert">{error}</p><Link className="results-primary hover-sweep" to="/">{copy.back}<Icon name="arrow"/></Link></section>
  if (!data) return <section className="results-page"><h1>{r.title}</h1><p role="status">{r.loading}</p></section>
  const hand = data.check.tests[0]?.hand
  return <section className="results-page" aria-labelledby="results-title">
    <h1 id="results-title">{r.title}</h1>
    <p className="lead"><Icon name="clock" size={18}/> {sinceDose(data.check.minutes_since_dose)}{hand && <> · {hand === 'left' ? copy.flow.leftHand : copy.flow.rightHand}</>}</p>
    <div className="results-grid">{data.cards.map(card => <article key={card.test} className={`result-card is-${card.status}`}>
      <h2>{r.tests[card.test]}</h2>
      <strong className="result-value">{cardValue(card)}</strong>
      <p className="muted">{r.help[card.test]}</p>
      <p className="result-baseline">{cardBaseline(card)}</p>
    </article>)}</div>
    <div className="results-actions">
      {hand
        ? <><Link className="results-primary hover-sweep" to="/check/connect" onClick={() => newCheck(otherHand(hand))}>{copy.flow.checkHand[otherHand(hand)]}<Icon name="arrow"/></Link><Link className="results-secondary hover-sweep" to="/check/connect" onClick={() => newCheck(hand)}>{r.newCheck}</Link></>
        : <Link className="results-primary hover-sweep" to="/check/connect" onClick={() => newCheck()}>{r.newCheck}<Icon name="arrow"/></Link>}
      <Link className="results-secondary hover-sweep" to="/dashboard">{r.trends}</Link>
    </div>
  </section>
}
