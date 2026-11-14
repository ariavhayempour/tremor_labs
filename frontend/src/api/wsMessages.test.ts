import { expect, test } from 'vitest'
import { parseMessage } from './wsMessages'
const s = (v: unknown) => JSON.stringify(v)

test('accepts every contract message type', () => {
  expect(parseMessage(s({ type: 'imu', t0: 1, fs: 100, samples: [[0, 0, 9.8, 0, 0, 0]] }))?.type).toBe('imu')
  expect(parseMessage(s({ type: 'tof', t0: 1, fs: 40, t: [0, 0.026], samples_mm: [212, 211] }))?.type).toBe('tof')
  expect(parseMessage(s({ type: 'spectrum', freqs: [0, 0.25], psd: [1, 2], peak_hz: null }))?.type).toBe('spectrum')
  expect(parseMessage(s({ type: 'position', tof_mm: null, in_band: false, band: [170, 230], valid_seconds: 0 }))?.type).toBe('position')
  expect(parseMessage(s({ type: 'status', recording: true, test_id: 4, test_type: 'rest', seconds_left: null }))?.type).toBe('status')
  expect(parseMessage(s({ type: 'source', sensor_source: 'board', connected: false, sensors: { movement: true, distance: false }, imu_hz: null, tof_hz: null }))?.type).toBe('source')
})

test('rejects malformed frames', () => {
  expect(parseMessage('not json')).toBeNull()
  expect(parseMessage(s({ type: 'imu', t0: 1, fs: 0, samples: [] }))).toBeNull()
  expect(parseMessage(s({ type: 'imu', t0: 1, fs: 100, samples: [[1, 2, 3]] }))).toBeNull()
  expect(parseMessage(s({ type: 'tof', t0: 1, fs: 40, t: [0], samples_mm: [1, 2] }))).toBeNull()
  expect(parseMessage(s({ type: 'unknown' }))).toBeNull()
})
