import type { Health, SimParams } from './types'
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
export const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1'
export class ApiError extends Error {
  status: number
  error: string
  constructor(status: number, error: string) { super(error); this.status = status; this.error = error }
}
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers }, signal: AbortSignal.timeout(5000) })
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { error?: string }
    throw new ApiError(response.status, body.error ?? response.statusText)
  }
  return response.json() as Promise<T>
}
export const getHealth = () => request<Health>('/api/health')
export const getSim = () => request<SimParams>('/api/sim')
export const putSim = (params: SimParams) => request<SimParams>('/api/sim', { method: 'PUT', body: JSON.stringify(params) })
