import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { copy } from '../copy'
import type { HandPoint } from '../dashboard/format'

export default function HandComparisonPlot({ data }: { data: HandPoint[] }) {
  return <div className="home-hand-chart" role="img" aria-label={copy.home.handChartLabel}>
    <ResponsiveContainer width="100%" height="100%" minWidth={0}>
      <LineChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: -24 }} accessibilityLayer>
        <CartesianGrid vertical={false} stroke="#e7edf7"/>
        <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#7a8ca4', fontSize: 10 }}/>
        <YAxis domain={[0, 4]} ticks={[0, 2, 4]} axisLine={false} tickLine={false} tick={{ fill: '#7a8ca4', fontSize: 10 }}/>
        <Tooltip formatter={(value, name) => [`${Number(value).toFixed(2)} ${copy.home.tapUnits}`, name]}/>
        <Line name={copy.flow.leftHand} dataKey="left" type="linear" stroke="#4a86fa" strokeWidth={2} dot={{ r: 3, fill: '#4a86fa', stroke: '#fff', strokeWidth: 1.5 }} activeDot={{ r: 5 }} isAnimationActive={false} connectNulls/>
        <Line name={copy.flow.rightHand} dataKey="right" type="linear" stroke="#274b7a" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3, fill: '#274b7a', stroke: '#fff', strokeWidth: 1.5 }} activeDot={{ r: 5 }} isAnimationActive={false} connectNulls/>
      </LineChart>
    </ResponsiveContainer>
  </div>
}
