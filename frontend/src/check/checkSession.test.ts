import { expect, test, vi } from 'vitest'
import { availableStep, connectCheck, finishRun, freshSession, initialSession, isComplete, readSession, skipStep, storageKey } from './checkSession'
test('future steps cannot be completed before connection', () => {
  expect(finishRun(initialSession, 'rest')).toBe(initialSession)
})
test('three reaches and both hands are needed before check completion', () => {
  let session = initialSession
  for (const step of ['connect', 'rest', 'posture'] as const) session = finishRun(session, step)
  expect(availableStep(session)).toBe(3)
  for (let i = 0; i < 2; i++) session = finishRun(session, 'reach')
  expect(isComplete(session, 'reach')).toBe(false)
  session = finishRun(session, 'reach')
  session = finishRun(session, 'tap')
  expect(isComplete(session, 'tap')).toBe(false)
  session = finishRun(session, 'tap')
  expect(availableStep(session)).toBe(5)
  expect(session.records.tap?.seconds).toBe(20)
  expect(finishRun(session, 'tap')).toBe(session)
})
test('connecting a check stores its id and completes the connect step', () => {
  const session = connectCheck(freshSession('sensor'), 12, 'left', 90)
  expect(session).toMatchObject({ checkId: 12, hand: 'left', minutesSinceDose: 90 })
  expect(isComplete(session, 'connect')).toBe(true)
})
test('skipping completes only the current step', () => {
  const session = connectCheck(freshSession('sensor'), 1, 'right', null)
  expect(skipStep(session, 'posture')).toBe(session)
  const skipped = skipStep(session, 'rest')
  expect(skipped.records.rest).toMatchObject({ runs: 1, skipped: true })
  expect(availableStep(skipped)).toBe(2)
})
test('sensor sessions survive a reload only with their check id', () => {
  const store = new Map<string, string>()
  vi.stubGlobal('sessionStorage', { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => store.set(k, v) })
  store.set(storageKey, JSON.stringify(skipStep(connectCheck(freshSession('sensor'), 7, 'right', null), 'rest')))
  expect(readSession()).toMatchObject({ mode: 'sensor', checkId: 7, hand: 'right', minutesSinceDose: null })
  expect(readSession().records.rest?.skipped).toBe(true)
  store.set(storageKey, JSON.stringify({ mode: 'sensor', records: { connect: { runs: 1 } } }))
  expect(readSession()).toEqual(freshSession('sensor'))
  vi.unstubAllGlobals()
})
