import { expect, test } from 'vitest'
import { availableStep, finishRun, initialSession, isComplete } from './checkSession'
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
