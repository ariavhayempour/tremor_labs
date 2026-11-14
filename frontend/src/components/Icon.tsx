export function Icon({ name, size = 22 }: { name: string; size?: number }) {
  const paths: Record<string, string> = {
    home: 'M3 10 12 3l9 7v10H3Z M9 20v-7h6v7', dashboard: 'M4 20V12m8 8V4m8 16V8',
    report: 'M6 3h9l4 4v14H6Z M10 11h5m-5 4h5', settings: 'M4 7h16M4 17h16 M9 4v6m6 4v6',
    dev: 'm8 6-6 6 6 6m8-12 6 6-6 6m-3-14-2 16', arrow: 'M4 12h16m-6-6 6 6-6 6',
    shield: 'm12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z m-4 9 3 3 5-6',
    clock: 'M12 7v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
    rest: 'M3 16h7l4-4h7M5 20h14M8 12l3-5 3 2', posture: 'M4 16h16M8 16V6m0 0-3 3m3-3 3 3',
    reach: 'M5 4h14M12 7v12m-5-5 5 5 5-5', tap: 'M9 20V9a2 2 0 0 1 4 0v5l3-2 4 3-3 6H9l-5-6 2-2 3 3 M13 3v1m5 1-1 1',
    wave: 'M2 12h4l3-8 5 16 3-8h5', menu: 'M4 6h16M4 12h16M4 18h16',
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.wave} /></svg>
}
