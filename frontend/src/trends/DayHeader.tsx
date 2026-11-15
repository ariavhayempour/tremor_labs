import { useEffect, useRef } from 'react'
import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { fmtMeasure, longDate, shortDate } from './format'
import { dosesOn, meanOf, position, type Range, type TrendDay } from './model'
import type { DoseOut } from '../api/types'
const t = copy.trends

interface Props { day: TrendDay; prev?: TrendDay; next?: TrendDay; doses: DoseOut[]; restRange: Range | null; onBack: () => void; onStep: (date: string) => void }

/** The day's title, its headline facts, and large previous/next day buttons. */
export function DayHeader({ day, prev, next, doses, restRange, onBack, onStep }: Props) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus({ preventScroll: true }) }, [day.date])
  const rest = meanOf(day.checks, 'rest'), where = position(rest, restRange)
  return <>
    <button type="button" className="trends-back" onClick={onBack}><Icon name="back" size={18}/>{t.back}</button>
    <div className="trends-day-head">
      <div>
        <h1 ref={heading} tabIndex={-1}>{longDate(day.date)}</h1>
        <p className="trends-facts">
          <span>{t.avgRest} <strong>{fmtMeasure('rest', rest)}</strong></span>
          {where && <span><strong>{t[where].charAt(0).toUpperCase() + t[where].slice(1)}</strong></span>}
          <span><strong>{day.checks.length}</strong> {t.checks}</span>
          <span><strong>{dosesOn(doses, day.date).length}</strong> {t.dosesLogged}</span>
        </p>
      </div>
      <div className="trends-stepper">
        <button type="button" disabled={!prev} onClick={() => prev && onStep(prev.date)} aria-label={prev ? `${t.prevDay}, ${longDate(prev.date)}` : t.prevDay}><Icon name="chevronLeft" size={18}/>{prev ? shortDate(prev.date) : t.prevDay}</button>
        <button type="button" disabled={!next} onClick={() => next && onStep(next.date)} aria-label={next ? `${t.nextDay}, ${longDate(next.date)}` : t.nextDay}>{next ? shortDate(next.date) : t.nextDay}<Icon name="chevronRight" size={18}/></button>
      </div>
    </div>
  </>
}
