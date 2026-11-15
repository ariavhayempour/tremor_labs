import { USE_FIXTURES } from '../api/client'
import type { Hand } from '../api/types'
/** Get-ready seconds shown after Start, before recording begins. */
export const COUNTDOWN_S = 3
export const steps = ['connect', 'rest', 'posture', 'reach', 'tap'] as const
export type CheckStep = typeof steps[number]
export type TestStep = Exclude<CheckStep, 'connect'>
export type Mode = 'demo' | 'sensor'
export interface SignalPoint { t: number; value: number }
export interface StepRecord { runs: number; seconds: number; samples?: SignalPoint[]; skipped?: boolean }
/** Sensor mode also tracks the backend check this browser session is filling in. */
export interface CheckSession { mode: Mode; records: Partial<Record<CheckStep, StepRecord>>; checkId?: number; hand?: Hand; minutesSinceDose?: number | null }
export const storageKey = 'tremor-check-v2'
// Without the backend (fixture mode) only the simulated demo can run.
export const defaultMode: Mode = USE_FIXTURES ? 'demo' : 'sensor'
export const initialSession: CheckSession = { mode: 'demo', records: {} }
export const freshSession = (mode: Mode): CheckSession => ({ ...initialSession, mode })
export const requiredRuns = (step: CheckStep) => step === 'reach' ? 3 : step === 'tap' ? 2 : 1
export const runSeconds = (step: CheckStep) => step === 'connect' ? 0 : step === 'reach' ? 6 : step === 'tap' ? 10 : 30
export const isComplete = (session: CheckSession, step: CheckStep) => (session.records[step]?.runs ?? 0) >= requiredRuns(step)
export function availableStep(session: CheckSession): number {
  const index = steps.findIndex(step => !isComplete(session, step))
  return index < 0 ? steps.length : index
}
export function finishRun(session: CheckSession, step: CheckStep, samples?: SignalPoint[]): CheckSession {
  if (steps.indexOf(step) > availableStep(session) || isComplete(session, step)) return session
  const previous = session.records[step] ?? { runs: 0, seconds: 0 }
  return { ...session, records: { ...session.records, [step]: { runs: previous.runs + 1, seconds: previous.seconds + runSeconds(step), samples: samples?.slice(-700) } } }
}
/** Marks every remaining run of the current step as done without data; Results shows it as missing. */
export function skipStep(session: CheckSession, step: TestStep): CheckSession {
  if (steps.indexOf(step) !== availableStep(session)) return session
  const previous = session.records[step] ?? { runs: 0, seconds: 0 }
  return { ...session, records: { ...session.records, [step]: { ...previous, runs: requiredRuns(step), skipped: true } } }
}
export function connectCheck(session: CheckSession, checkId: number, hand: Hand, minutesSinceDose: number | null): CheckSession {
  return finishRun({ ...session, checkId, hand, minutesSinceDose }, 'connect')
}
export function readSession(defaultMode: Mode = 'demo'): CheckSession {
  const fallback = freshSession(defaultMode)
  try {
    const data: unknown = JSON.parse(sessionStorage.getItem(storageKey) ?? 'null')
    if (!data || typeof data !== 'object' || !('mode' in data) || !('records' in data) || !['demo', 'sensor'].includes(String(data.mode))) return fallback
    const records = data.records
    if (!records || typeof records !== 'object') return fallback
    const session: CheckSession = { mode: data.mode as Mode, records: {} }
    const checkId: unknown = Reflect.get(data, 'checkId')
    const hand: unknown = Reflect.get(data, 'hand')
    const minutes: unknown = Reflect.get(data, 'minutesSinceDose')
    if (Number.isInteger(checkId)) session.checkId = Number(checkId)
    if (hand === 'left' || hand === 'right') session.hand = hand
    if (minutes === null || (typeof minutes === 'number' && Number.isFinite(minutes))) session.minutesSinceDose = minutes
    if (session.mode === 'sensor' && session.checkId === undefined) return freshSession('sensor')
    for (const step of steps) {
      const value: unknown = Reflect.get(records, step)
      if (value && typeof value === 'object' && 'runs' in value && Number.isInteger(value.runs) && Number(value.runs) > 0 && Number(value.runs) <= requiredRuns(step)) {
        const rawSamples: unknown = 'samples' in value ? value.samples : undefined
        const samples: SignalPoint[] = []
        if (Array.isArray(rawSamples)) for (const point of rawSamples.slice(-700)) {
          if (point && typeof point === 'object' && 't' in point && 'value' in point && typeof point.t === 'number' && typeof point.value === 'number' && Number.isFinite(point.t) && Number.isFinite(point.value)) samples.push({ t: point.t, value: point.value })
        }
        const skipped = 'skipped' in value && value.skipped === true
        session.records[step] = { runs: Number(value.runs), seconds: Number(value.runs) * runSeconds(step), samples, ...(skipped ? { skipped } : {}) }
      } else break
      if (!isComplete(session, step)) break
    }
    return session
  } catch { return fallback }
}
