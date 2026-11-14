// Mirrors docs/contracts.md. Field names match the backend's JSON exactly.
export type SensorSource = 'sim' | 'board' | 'replay'
export type TestType = 'rest' | 'posture' | 'reach' | 'tap'
export type Hand = 'left' | 'right'
export type TestStatus = 'recording' | 'analyzing' | 'done' | 'failed'
export type FailReason = 'insufficient_valid_data' | 'no_descent_detected' | 'no_taps_detected' | 'sensor_disconnected' | 'interrupted'
export type LedCommand = 'countdown' | 'hold' | 'check' | 'idle' | 'clear' | 'recording'
export type Medication = 'now' | 'hours_ago' | 'not_yet'
export interface Sensors { movement: boolean; distance: boolean }

export interface Health { status: 'ok'; sensor_source: SensorSource; connected: boolean; sensors_detected: Sensors; imu_hz: number | null; tof_hz: number | null }
export interface SimParams { tremor_hz: number; tremor_amp: number; noise: number; hand_mm: number; reach_wobble: number }
export type SimUpdateRequest = Partial<SimParams> & { action?: 'descent' }
export const defaultSim: SimParams = { tremor_hz: 5, tremor_amp: 0.3, noise: 0.02, hand_mm: 200, reach_wobble: 0 }

export interface CheckInRequest { medication: Medication; hours_ago?: number | null; notes?: string | null }
export interface CheckCreated { check_id: number; minutes_since_dose: number | null }

export interface ResultOut {
  peak_hz: number | null; strength_ms2: number | null; strength_score: number | null; tremor_detected: boolean | null; valid_seconds: number | null
  smoothness: number | null; wobble_ratio: number | null
  taps_per_sec: number | null; tap_amplitude: number | null; amplitude_decrement: number | null; rhythm_cv: number | null
  details: Record<string, unknown>
}
export interface TestOut { id: number; type: TestType; hand: Hand; status: TestStatus; fail_reason: FailReason | null; result: ResultOut | null }
export interface CheckOut { id: number; created_at: string; minutes_since_dose: number | null; notes: string | null; dose_id: number | null; tests: TestOut[] }
export interface Card { test: TestType; metric: 'strength_score' | 'smoothness' | 'taps_per_sec'; value: number | null; unit: 'score' | 'mm' | 'taps/s'; baseline_pct: number | null; baseline_n: number; status: 'done' | 'failed' | 'missing' }
export interface CheckSummaryOut { check: CheckOut; cards: Card[] }

export interface StartTestRequest { type: TestType; hand: Hand }
export interface TestStarted { test_id: number }
export interface TestOutcome { test_id: number; status: TestStatus; fail_reason: FailReason | null; result: ResultOut | null }
export interface TapFrame { t_ms: number; lm: [number, number][] | null }
export interface TapDataIn { frames: TapFrame[] }

export interface DoseOut { id: number; taken_at: string; label: string | null }
export interface Bin { start_h: number; mean: number; count: number }
export interface DoseResponseOut { bins: Bin[]; returns_after_h: number | null; doses: DoseOut[] }
export interface ProfileRow { test_type: TestType; first_week: number | null; first_n: number; current: number | null; current_n: number }
export interface DayPoint { date: string; mean_rest: number | null; count: number }
export interface InsightsSummary { checks_completed: number; streak_days: number; returns_after_h: number | null; daily: DayPoint[] }
export interface ReportOut { period: { start: string; end: string }; checks_completed: number; dose_response: Bin[]; returns_after_h: number | null; profile: ProfileRow[]; daily: DayPoint[]; generated_at: string }

export interface SettingsModel { dose_times: string[]; reminder_times: string[]; tested_hand: Hand; posture_band: [number, number] | null }
export type SettingsUpdate = Partial<SettingsModel>
export interface LedRequest { command: LedCommand; value?: number | null }

export interface ImuMsg { type: 'imu'; t0: number; fs: number; samples: number[][] }
export interface TofMsg { type: 'tof'; t0: number; fs: number; t: number[]; samples_mm: number[] }
export interface SpectrumMsg { type: 'spectrum'; freqs: number[]; psd: number[]; peak_hz: number | null }
export interface PositionMsg { type: 'position'; tof_mm: number | null; in_band: boolean; band: [number, number]; valid_seconds: number }
export interface StatusMsg { type: 'status'; recording: boolean; test_id: number | null; test_type: TestType | null; seconds_left: null }
export interface SourceMsg { type: 'source'; sensor_source: SensorSource; connected: boolean; sensors: Sensors; imu_hz: number | null; tof_hz: number | null }
export type WsMessage = ImuMsg | TofMsg | SpectrumMsg | PositionMsg | StatusMsg | SourceMsg
