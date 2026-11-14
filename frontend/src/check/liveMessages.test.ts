import { expect, test } from 'vitest'
import type { Health, PositionMsg } from '../api/types'
import { copy } from '../copy'
import { bandMessage, healthProblems } from './liveMessages'
const health = (connected: boolean, movement: boolean, distance: boolean): Health => ({ status: 'ok', sensor_source: 'board', connected, sensors_detected: { movement, distance }, imu_hz: null, tof_hz: null })
const at = (tof_mm: number | null): PositionMsg => ({ type: 'position', tof_mm, in_band: false, band: [170, 230], valid_seconds: 0 })

test('a dropped board link hides the per-sensor messages', () => {
  expect(healthProblems(health(false, false, false))).toEqual([copy.sensorCheck.boardOffline])
  expect(healthProblems(health(true, false, true))).toEqual([copy.sensorCheck.missingMovement])
  expect(healthProblems(health(true, true, true))).toEqual([])
})
test('band prompts follow the contract: below band[0] is too low', () => {
  expect(bandMessage(null)).toBe(copy.sensorCheck.noReading)
  expect(bandMessage(at(null))).toBe(copy.sensorCheck.noReading)
  expect(bandMessage(at(150))).toBe(copy.sensorCheck.tooLow)
  expect(bandMessage(at(250))).toBe(copy.sensorCheck.tooHigh)
  expect(bandMessage(at(200))).toBe(copy.sensorCheck.inBand)
})
