import { Bar, BarChart, CartesianGrid, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Bin } from '../api/types'
import { copy } from '../copy'
import { doseBars } from './format'
const d = copy.dashboard

export default function DoseCurvePlot({ bins, returnsAfter }: { bins: Bin[]; returnsAfter: number | null }) {
  return <div className="home-chart dose-chart" role="img" aria-label={d.curveLabel}>
    <ResponsiveContainer width="100%" height="100%" minWidth={0}>
      <BarChart data={doseBars(bins)} margin={{ top: 24, right: 8, bottom: 16, left: 0 }}>
        <CartesianGrid vertical={false} stroke="#e7edf7"/>
        <XAxis dataKey="h" type="number" domain={[0, 6]} ticks={[0, 1, 2, 3, 4, 5, 6]} axisLine={false} tickLine={false} tick={{ fill: '#7a8ca4', fontSize: 10 }} label={{ value: d.hoursSince, position: 'insideBottom', offset: -10, fill: '#7a8ca4', fontSize: 11 }}/>
        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#7a8ca4', fontSize: 10 }} tickFormatter={v => Number(v).toFixed(2)} width={44}/>
        <Tooltip cursor={{ fill: '#eaf3ff' }} labelFormatter={(_, payload) => String(payload?.[0]?.payload?.label ?? '')} formatter={(value, _name, item) => [`${Number(value).toFixed(3)} m/s² · n=${String(item.payload.count)}`, d.strength]}/>
        {returnsAfter !== null && <ReferenceLine x={returnsAfter} stroke="#274b7a" strokeDasharray="5 4"/>}
        <Bar dataKey="mean" fill="#4a86fa" radius={[5, 5, 0, 0]} barSize={22}><LabelList dataKey="count" position="top" fill="#66819d" fontSize={10}/></Bar>
      </BarChart>
    </ResponsiveContainer>
  </div>
}
