export type KeyMark = 'line' | 'dash' | 'band' | 'dot' | 'hollow' | 'dose'

/** A chart legend; marks differ in shape as well as colour. */
export function ChartKey({ items }: { items: [KeyMark, string][] }) {
  return <div className="trends-key" aria-hidden="true">{items.map(([mark, label]) => <span key={label}><i className={`trends-mark ${mark}`}/>{label}</span>)}</div>
}
