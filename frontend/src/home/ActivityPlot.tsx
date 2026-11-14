import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { copy } from '../copy'
import { dailyCounts, type HistoryEntry } from './homeStore'
/** `data` (per-day counts from the backend) replaces counts derived from local history. */
export default function ActivityPlot({ history, days = 7, data }: { history: HistoryEntry[]; days?: number; data?: { day: string; count: number }[] }) {
  return <div className="home-chart" role="img" aria-label={copy.home.activityChart}><ResponsiveContainer width="100%" height="100%" minWidth={0}><BarChart data={data ?? dailyCounts(history, days)} margin={{ top: 24, right: 8, bottom: 0, left: -24 }} barSize={days === 7 ? 24 : 16}><CartesianGrid vertical={false} stroke="#e7edf7"/><XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#7a8ca4', fontSize: 10 }}/><YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#7a8ca4', fontSize: 10 }}/><Tooltip cursor={{ fill: '#eaf3ff' }} formatter={value => [value, copy.home.checks]}/><Bar dataKey="count" fill="#4a86fa" radius={[5,5,0,0]}><LabelList dataKey="count" position="top" fill="#66819d" fontSize={10}/></Bar></BarChart></ResponsiveContainer></div>
}
