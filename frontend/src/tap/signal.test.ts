import { describe, expect, it } from 'vitest'
import { LiveTapCounter, opening, tapLandmarks } from './signal'
describe('camera tap signal', () => {
  it('sends landmarks in contract order and preserves missing hands', () => {
    const points = Array.from({ length: 21 }, (_, i) => ({ x: i / 21, y: 0.5 }))
    expect(tapLandmarks(points)).toEqual([0, 4, 8, 9].map(i => [i / 21, 0.5]))
    expect(tapLandmarks()).toBeNull()
    expect(tapLandmarks([{ x: NaN, y: 0 }])).toBeNull()
  })
  it('normalizes opening by hand size and rejects a degenerate hand', () => {
    expect(opening([[0, 0], [0, 0], [0.5, 0], [1, 0]])).toBe(0.5)
    expect(opening([[0, 0], [0, 0], [1, 0], [2, 0]])).toBe(0.5)
    expect(opening([[0, 0], [0, 0], [1, 0], [0, 0]])).toBeNull()
  })
  it('counts 4 Hz taps and ignores noise and lost-hand transitions', () => {
    const counter = new LiveTapCounter()
    for (let i = 0; i < 600; i++) counter.push(0.4 + 0.35 * Math.sin(i / 60 * Math.PI * 8))
    expect(counter.count).toBeGreaterThanOrEqual(38)
    expect(counter.count).toBeLessThanOrEqual(42)
    const noise = new LiveTapCounter()
    for (let i = 0; i < 100; i++) noise.push(0.2 + 0.02 * Math.sin(i))
    noise.push(0.8); noise.push(null); noise.push(0.1)
    expect(noise.count).toBe(0)
  })
})
