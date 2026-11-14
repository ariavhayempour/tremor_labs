export const steps = ['connect', 'rest', 'posture', 'reach', 'tap'] as const
export type CheckStep = typeof steps[number]
export type Mode = 'demo' | 'sensor'
export interface SignalPoint { t: number; value: number }
export interface StepRecord { runs: number; seconds: number; samples?: SignalPoint[] }
export interface CheckSession { mode: Mode; records: Partial<Record<CheckStep, StepRecord>> }
export const storageKey = 'tremor-check-v1'
export const initialSession: CheckSession = { mode: 'demo', records: {} }
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
export function readSession(): CheckSession {
  try {
    const data: unknown = JSON.parse(sessionStorage.getItem(storageKey) ?? 'null')
    if (!data || typeof data !== 'object' || !('mode' in data) || !('records' in data) || !['demo', 'sensor'].includes(String(data.mode))) return initialSession
    const records = data.records
    if (!records || typeof records !== 'object') return initialSession
    const session: CheckSession = { mode: data.mode as Mode, records: {} }
    for (const step of steps) {
      const value: unknown = Reflect.get(records, step)
      if (value && typeof value === 'object' && 'runs' in value && Number.isInteger(value.runs) && Number(value.runs) > 0 && Number(value.runs) <= requiredRuns(step)) {
        const rawSamples: unknown = 'samples' in value ? value.samples : undefined
        const samples: SignalPoint[] = []
        if (Array.isArray(rawSamples)) for (const point of rawSamples.slice(-700)) {
          if (point && typeof point === 'object' && 't' in point && 'value' in point && typeof point.t === 'number' && typeof point.value === 'number' && Number.isFinite(point.t) && Number.isFinite(point.value)) samples.push({ t: point.t, value: point.value })
        }
        session.records[step] = { runs: Number(value.runs), seconds: Number(value.runs) * runSeconds(step), samples }
      } else break
      if (!isComplete(session, step)) break
    }
    return session
  } catch { return initialSession }
}
