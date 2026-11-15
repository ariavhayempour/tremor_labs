import { Icon } from '../components/Icon'
import { copy } from '../copy'
import { fmtMeasure, longDate, shortDate, weekday } from './format'
import { meanOf, position, type Range, type TrendDay } from './model'
const t = copy.trends

/** Every day as a large row with each test's daily average: the charts' table view and their easiest tap target. */
export function DayList({ days, restRange, onPick }: { days: TrendDay[]; restRange: Range | null; onPick: (date: string) => void }) {
  return <div className="trends-daylist">
    <div className="trends-dl-head" aria-hidden="true"><span>{t.day}</span><span>{t.restCol}<small>{t.units.score}</small></span><span>{t.postureCol}<small>{t.units.score}</small></span><span>{t.reachCol}<small>{t.units.mm}</small></span><span>{t.tapCol}<small>{t.units.taps}</small></span><span/></div>
    <ul>{[...days].reverse().map(d => {
      const rest = meanOf(d.checks, 'rest'), where = position(rest, restRange)
      const cells = [['rest', t.restShort], ['posture', t.postureShort], ['reach', t.reachShort], ['tap', t.tapShort]] as const
      return <li key={d.date}><button type="button" className="trends-dl-row" onClick={() => onPick(d.date)}
        aria-label={`${longDate(d.date)}: ${cells.map(([k, l]) => `${l} ${fmtMeasure(k, meanOf(d.checks, k))}`).join(', ')}${where && where !== 'within' ? `, ${t.statusShort[where]}` : ''}; ${d.checks.length} ${t.checks}. ${t.openDayLabel}`}>
        <span className="trends-dl-day">{weekday(d.date)} {shortDate(d.date)}<small>{d.checks.length} {d.checks.length === 1 ? t.check : t.checks}</small></span>
        {cells.map(([k, l]) => <span key={k} className="trends-dl-value"><span className="trends-dl-label">{l}</span>{fmtMeasure(k, meanOf(d.checks, k))}
          {k === 'rest' && where && where !== 'within' && <small><Icon name={where === 'above' ? 'up' : 'down'} size={12}/>{t.statusShort[where]}</small>}</span>)}
        <Icon name="chevronRight" size={18}/>
      </button></li>
    })}</ul>
  </div>
}
