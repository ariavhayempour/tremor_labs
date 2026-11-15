import type {
  CheckCreated, CheckInRequest, CheckOut, CheckSummaryOut, DoseOut, DoseResponseOut, Health, InsightsSummary, LedCommand,
  ProfileRow, ReportOut, SettingsModel, SettingsUpdate, SimParams, SimUpdateRequest, StartTestRequest, TapDataIn, TestOutcome, TestStarted,
} from './types'
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
export const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1'
const TIMEOUT_MS = 10000
export class ApiError extends Error {
  status: number
  error: string
  constructor(status: number, error: string) { super(error); this.status = status; this.error = error }
}
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers }, signal: AbortSignal.timeout(TIMEOUT_MS) })
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { error?: string }
    throw new ApiError(response.status, body.error ?? response.statusText)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
const post = <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
const put = <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) })
const days = (n: number) => `?days=${n}`

export const getHealth = () => request<Health>('/api/health')
export const getSim = () => request<SimParams>('/api/sim')
export const putSim = (update: SimUpdateRequest) => put<SimParams>('/api/sim', update)
export const triggerDescent = () => putSim({ action: 'descent' })

export const createCheck = (body: CheckInRequest) => post<CheckCreated>('/api/checks', body)
export function listChecks(params: { from?: string; to?: string; details?: boolean } = {}) {
  const q = new URLSearchParams()
  if (params.from) q.set('from', params.from)
  if (params.to) q.set('to', params.to)
  if (params.details !== undefined) q.set('details', String(params.details))
  const query = q.toString()
  return request<CheckOut[]>(`/api/checks${query ? `?${query}` : ''}`)
}
export const getCheck = (checkId: number) => request<CheckSummaryOut>(`/api/checks/${checkId}`)
export const startTest = (checkId: number, body: StartTestRequest) => post<TestStarted>(`/api/checks/${checkId}/tests`, body)
export const stopTest = (testId: number) => post<TestOutcome>(`/api/tests/${testId}/stop`)
export const markTest = (testId: number) => post<undefined>(`/api/tests/${testId}/mark`)
export const sendTapData = (testId: number, body: TapDataIn) => post<TestOutcome>(`/api/tests/${testId}/tap-data`, body)

export const getDoses = () => request<DoseOut[]>('/api/doses')
export const getDoseResponse = (n = 14) => request<DoseResponseOut>(`/api/insights/dose-response${days(n)}`)
export const getProfile = (n = 14) => request<ProfileRow[]>(`/api/insights/profile${days(n)}`)
export const getSummary = (n = 14) => request<InsightsSummary>(`/api/insights/summary${days(n)}`)
export const getReport = (n = 14) => request<ReportOut>(`/api/report${days(n)}`)
export const getSettings = () => request<SettingsModel>('/api/settings')
export const putSettings = (update: SettingsUpdate) => put<SettingsModel>('/api/settings', update)

// LED cues are best effort: a failure must never interrupt a check.
export function led(command: LedCommand, value?: number) {
  if (USE_FIXTURES) return
  void post<undefined>('/api/led', { command, value: value ?? null }).catch(() => undefined)
}
