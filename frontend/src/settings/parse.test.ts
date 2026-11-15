import { expect, test } from 'vitest'
import { parseBand, parseTimes } from './parse'
test('times are 24-hour HH:MM, comma separated', () => {
  expect(parseTimes('08:00, 13:00,18:30')).toEqual(['08:00', '13:00', '18:30'])
  expect(parseTimes('8:00')).toEqual(['08:00'])
  expect(parseTimes('')).toEqual([])
  expect(parseTimes('24:00')).toBeNull()
  expect(parseTimes('noon')).toBeNull()
})
test('band follows the backend limits', () => {
  expect(parseBand('170', '230')).toEqual([170, 230])
  expect(parseBand('230', '170')).toBeNull()
  expect(parseBand('0', '2500')).toBeNull()
  expect(parseBand('', '200')).toBeNull()
})
