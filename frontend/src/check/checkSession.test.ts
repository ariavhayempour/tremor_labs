import { expect, test, vi } from 'vitest'
import { availableStep, chooseHand, connectCheck, finishRun, freshSession, initialSession, isComplete, otherHand, readSession, skipStep, storageKey } from './checkSession'
test('future steps cannot be completed before connection', () => {
  expect(finishRun(initialSession, 'rest')).toBe(initialSession)
})
test('three reaches and one tap run are needed before check completion', () => {
  let session = initialSession
  for (const step of ['connect', 'rest', 'posture'] as const) session = finishRun(session, step)
  expect(availableStep(session)).toBe(3)
  for (let i = 0; i < 2; i++) session = finishRun(session, 'reach')
  expect(isComplete(session, 'reach')).toBe(false)
  session = finishRun(session, 'reach')
  session = finishRun(session, 'tap')
  expect(availableStep(session)).toBe(5)
  expect(session.records.tap?.seconds).toBe(10)
  expect(finishRun(session, 'tap')).toBe(session)
})
test('the hand is chosen before connecting and then stays fixed', () => {
  const left = chooseHand(freshSession('sensor'), 'left')
  expect(left.hand).toBe('left')
  const connected = connectCheck(left, 3, null)
  expect(chooseHand(connected, 'right')).toBe(connected)
  expect(otherHand('left')).toBe('right')
  expect(freshSession('demo', otherHand(connected.hand)).hand).toBe('right')
})
test('connecting a check stores its id and completes the connect step', () => {
  const session = connectCheck(freshSession('sensor', 'left'), 12, 90)
  expect(session).toMatchObject({ checkId: 12, hand: 'left', minutesSinceDose: 90 })
  expect(isComplete(session, 'connect')).toBe(true)
})
test('skipping completes only the current step', () => {
  const session = connectCheck(freshSession('sensor'), 1, null)
  expect(skipStep(session, 'posture')).toBe(session)
  const skipped = skipStep(session, 'rest')
  expect(skipped.records.rest).toMatchObject({ runs: 1, skipped: true })
  expect(availableStep(skipped)).toBe(2)
})
test('sensor sessions survive a reload only with their check id', () => {
  const store = new Map<string, string>()
  vi.stubGlobal('sessionStorage', { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => store.set(k, v) })
  store.set(storageKey, JSON.stringify(skipStep(connectCheck(freshSession('sensor', 'left'), 7, null), 'rest')))
  expect(readSession()).toMatchObject({ mode: 'sensor', checkId: 7, hand: 'left', minutesSinceDose: null })
  expect(readSession().records.rest?.skipped).toBe(true)
  store.set(storageKey, JSON.stringify({ mode: 'sensor', hand: 'left', records: { connect: { runs: 1 } } }))
  expect(readSession()).toEqual(freshSession('sensor', 'left'))
  vi.unstubAllGlobals()
})
