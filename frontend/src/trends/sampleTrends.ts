import type { CheckOut, DoseOut, Hand, ResultOut, TestOut, TestType } from '../api/types'
import { windowStart } from '../dashboard/format'

/** Synthetic checks and doses in the backend's shapes. Deterministic for a given `now` and `days`; each sitting is a left-hand check then a right-hand check. */
export interface SampleTrends { checks: CheckOut[]; doses: DoseOut[] }

const DOSE_TIMES = [8 * 60, 13 * 60, 18 * 60]
// Rest strength (m/s²) rises along a logistic curve as a dose wears off, mirroring the backend seeder.
const FLOOR_MS2 = 0.06, RANGE_MS2 = 0.34, MID_H = 3.0, WIDTH_H = 0.5, ONSET_H = 1.0, NOISE = 0.12
const RHYTHM_MIN_MS2 = 0.08
// The second hand's check starts this many minutes after the first; the right hand reads a little stronger so the comparison has something to show.
const HAND_GAP_MIN = 5
const HANDS: { hand: Hand; offset: number; tremor: number; tap: number }[] = [{ hand: 'left', offset: 0, tremor: 1, tap: 4.2 }, { hand: 'right', offset: HAND_GAP_MIN, tremor: 1.25, tap: 4.4 }]

const base = (h: number) => FLOOR_MS2 + RANGE_MS2 / (1 + Math.exp(-(h - MID_H) / WIDTH_H))
const score = (ms2: number) => ms2 <= 0.05 ? 0 : Math.min(100, 50 * Math.log10(ms2 / 0.05))
const round = (x: number, n: number) => Math.round(x * 10 ** n) / 10 ** n

function result(fields: Partial<ResultOut>): ResultOut {
  return { peak_hz: null, strength_ms2: null, strength_score: null, tremor_detected: null, valid_seconds: null, smoothness: null, wobble_ratio: null, taps_per_sec: null, tap_amplitude: null, amplitude_decrement: null, rhythm_cv: null, details: {}, ...fields }
}

export function sampleTrends(now: Date = new Date(), days = 14): SampleTrends {
  let seed = 42
  const rand = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296
  const gauss = () => { const u = rand() || 1e-9, v = rand(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v) }
  const uni = (a: number, b: number) => a + (b - a) * rand()
  const start = windowStart(days, now)
  const checks: CheckOut[] = [], doses: DoseOut[] = []
  let checkId = 1, testId = 1, doseId = 1
  for (let d = 0; d < days; d++) {
    const day = new Date(start); day.setDate(start.getDate() + d)
    const at = (minute: number) => { const t = new Date(day); t.setMinutes(Math.round(minute)); return t }
    const doseMin = DOSE_TIMES.map(m => m + uni(-10, 10))
    const dayDoses = doseMin.map(m => ({ id: doseId++, taken_at: at(m).toISOString(), label: null }))
    doses.push(...dayDoses)
    const n = rand() < 0.5 ? 3 : 4
    let times: number[]
    do { times = Array.from({ length: n }, () => uni(7.5 * 60, 21.5 * 60)).sort((a, b) => a - b) } while (!times.every((t, i) => i === 0 || t - times[i - 1] >= 30))
    for (const sitting of times) for (const side of HANDS) {
      const t = sitting + side.offset, hand = side.hand
      const when = at(t)
      if (when > now) continue
      const prior = doseMin.map((m, i) => ({ m, i })).filter(x => x.m <= t)
      const last = prior.at(-1) ?? null
      const h = last ? (t - last.m) / 60 : null
      const prevInterval = prior.length >= 2 ? (prior[prior.length - 1].m - prior[prior.length - 2].m) / 60 : null
      let clean: number
      if (h === null) clean = FLOOR_MS2 + RANGE_MS2
      else if (h >= ONSET_H) clean = base(h)
      else { const before = prevInterval === null ? FLOOR_MS2 + RANGE_MS2 : base(prevInterval); clean = before + (FLOOR_MS2 - before) * (h / ONSET_H) }
      const rest = Math.max(0.03, side.tremor * clean * (1 + NOISE * gauss()))
      const rel = rest / 0.4, posture = 0.7 * rest
      const hz = (ms2: number) => ms2 >= RHYTHM_MIN_MS2 ? round(uni(4.5, 5.5), 2) : null
      const tap = (speed: number): ResultOut => result({ taps_per_sec: round(speed, 2), tap_amplitude: round(uni(0.6, 0.9), 2), amplitude_decrement: round(uni(-0.15, -0.05), 3), rhythm_cv: round(0.08 + 0.1 * rel, 3) })
      const test = (type: TestType, testHand: Hand, r: ResultOut): TestOut => ({ id: testId++, type, hand: testHand, status: 'done', fail_reason: null, result: r })
      checks.push({
        id: checkId++, created_at: when.toISOString(), minutes_since_dose: h === null ? null : round(h * 60, 1), notes: null, dose_id: last ? dayDoses[last.i].id : null,
        tests: [
          test('rest', hand, result({ strength_ms2: round(rest, 3), strength_score: round(score(rest), 1), peak_hz: hz(rest), tremor_detected: rest >= RHYTHM_MIN_MS2, valid_seconds: 30 })),
          test('posture', hand, result({ strength_ms2: round(posture, 3), strength_score: round(score(posture), 1), peak_hz: hz(posture), tremor_detected: posture >= RHYTHM_MIN_MS2, valid_seconds: round(uni(22, 30), 1) })),
          test('reach', hand, result({ smoothness: round(2 + 4 * rel * (1 + 0.08 * gauss()), 2), wobble_ratio: round(1 + 1.5 * rel * (1 + 0.08 * gauss()), 2) })),
          test('tap', hand, tap(side.tap - 0.8 * rel + 0.15 * gauss())),
        ],
      })
    }
  }
  return { checks: checks.reverse(), doses }
}
