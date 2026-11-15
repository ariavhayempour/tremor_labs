import { useEffect, useRef } from 'react'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { Waveform } from '../viz/Waveform'
import { RingBuf } from '../viz/ringbuf'
import type { CheckStep, StepRecord } from './checkSession'

export function ResultCard({ step, record }: { step: Exclude<CheckStep, 'connect'>; record: StepRecord }) {
  const buffer = useRef(new RingBuf(1500, 1))
  useEffect(() => { buffer.current.clear(); record.samples?.forEach(point => buffer.current.push(point.t, [point.value])) }, [record])
  const text = copy.flow.steps[step]
  const axis = step === 'reach' ? copy.flow.distance : step === 'tap' ? copy.flow.fingerOpening : copy.axis
  return <section className="result-card" aria-labelledby={`result-${step}`}>
    <div className="result-card-heading"><span><Icon name={step} size={20}/><h2 id={`result-${step}`}>{text.label}</h2></span><span className="result-complete"><Icon name="check" size={14}/>{copy.flow.complete}</span></div>
    <div className="result-record"><strong>{step === 'reach' ? `${record.runs} ${copy.flow.resultAttempts}` : step === 'tap' ? `${record.runs} ${copy.flow.resultHands}` : `${record.seconds} ${copy.flow.resultSeconds}`}</strong><span>{step === 'tap' ? copy.flow.lastRightHand : step === 'reach' ? copy.flow.lastAttempt : copy.flow.lastWindow}</span></div>
    <div className="chart-label">{axis}</div>
    {record.samples?.length ? <Waveform buf={buffer} min={step === 'reach' || step === 'tap' ? 0 : -2} max={step === 'reach' ? 350 : step === 'tap' ? 1 : 2} seconds={step === 'reach' ? 6 : 5} label={text.graphLabel}/> : <div className="result-empty">{copy.flow.noSavedSignal}</div>}
    <div className="chart-bottom"><span>{copy.timeAxis}</span><span>n={record.samples?.length ?? 0} {copy.flow.resultSamples}</span></div>
  </section>
}
