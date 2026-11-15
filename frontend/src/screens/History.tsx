import { useState } from 'react'
import { USE_FIXTURES } from '../api/client'
import { LiveHistory } from '../dashboard/LiveHistory'
import { Link } from 'react-router'
import { copy } from '../copy'
import { Icon } from '../components/Icon'
import { SegmentedControl } from '../components/SegmentedControl'
import { ActivityChart } from '../home/ActivityChart'
import { dateLabel, readHistory, timeLabel } from '../home/homeStore'
/** Sample history from this browser; used only in fixture mode, without the backend. */
function SampleHistory() {
  const [history] = useState(readHistory)
  const [days, setDays] = useState(14)
  const [today] = useState(() => new Date().toISOString())
  const cutoff = new Date(today); cutoff.setDate(cutoff.getDate() - days + 1); cutoff.setHours(0,0,0,0)
  const filtered = history.filter(record => new Date(record.at) >= cutoff)
  return <div className="history-page"><div className="history-heading"><div><Link className="home-text-link" to="/"><Icon name="back" size={16}/>{copy.home.home}</Link><h1>{copy.home.historyTitle}</h1><p>{copy.home.sampleHistory}</p></div><SegmentedControl<number> className="history-period" label={copy.home.period} value={days} onChange={setDays} options={[{ value: 7, label: `7 ${copy.home.days}` }, { value: 14, label: `14 ${copy.home.days}` }]}/></div><section className="home-card history-chart-card"><h2>{filtered.length} {copy.home.checks}</h2><ActivityChart history={filtered} days={days}/></section><section className="home-card history-list"><h2>{copy.home.recentChecks}</h2><table><thead><tr><th>{copy.home.date}</th><th>{copy.home.time}</th><th>{copy.home.duration}</th><th>{copy.home.status}</th><th>{copy.home.source}</th></tr></thead><tbody>{filtered.map(record => <tr key={record.id}><td>{dateLabel(record.at)}</td><td>{timeLabel(record.at)}</td><td>{Math.floor(record.seconds / 60)}:{String(record.seconds % 60).padStart(2,'0')}</td><td><span className="history-completed"><Icon name="check" size={14}/>{copy.flow.complete}</span></td><td>{record.source === 'sample' ? copy.home.sample : copy.home.demoCheck}</td></tr>)}</tbody></table></section></div>
}
export const History = USE_FIXTURES ? SampleHistory : LiveHistory
