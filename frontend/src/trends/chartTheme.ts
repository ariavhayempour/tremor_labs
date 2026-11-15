// Chart colours from the app's blue palette; left hand is solid blue, right hand dashed navy so hands never rely on colour alone.
export const BLUE = '#346cf5'
export const NAVY = '#1d3c6e'
export const INK = '#0b1f3a'
export const MUTED = '#566c88'
export const GRID = '#e3eaf5'
export const BASELINE = '#c9d6ea'
export const HIGHLIGHT = '#eaf3ff'
export const DOSE = '#8a6a1f'
export const DOSE_INK = '#6b5216'
export const BAND_OPACITY = 0.09
/** Y-axis width plus the chart's right margin: the overlay buttons use these to line up with the plot area. */
export const PLOT_LEFT = 44
export const PLOT_RIGHT = 12
export const END_LABEL_RIGHT = 52

export const prefersReducedMotion = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Evenly spaced round tick values covering [lo, hi]. */
export function niceTicks(lo: number, hi: number, count = 5): number[] {
  const raw = (hi - lo) / count, mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map(s => s * mag).find(s => s >= raw) ?? raw
  const out: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(6)))
  return out
}
export const niceMax = (v: number, step: number) => Math.ceil(v / step) * step
