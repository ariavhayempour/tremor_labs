# Tremor Lab: Frontend Implementation Plan

> **How to use this plan:**
> - Work the tasks in order, F0 first.
> - Each step is one checkbox; tick it (`- [x]`) when its check passes.
> - With an AI coding agent, point it at this file and `CLAUDE.md`, and have it do one task at a time and stop at each **Checkpoint**.

**Goal:** Build the Tremor Lab browser app. It covers:
- the guided 2-minute check (check-in, then rest, posture, reach and tap tests, then results), with live sensor visualizations and a MediaPipe tap test;
- the 14-day dashboard;
- the printable doctor report;
- settings;
- a dev panel for the simulator.

**Architecture:**
- A Vite + React + TS app served only from `http://localhost:5173`. It talks to a FastAPI backend at `VITE_API_BASE` (default `http://localhost:8000`) over REST and a WebSocket at `/ws`.
- The frontend owns the check flow and its timing. The backend only records and analyzes.
- Streaming data lives in refs and is drawn on `<canvas>`. Dashboard charts use Recharts.

**Tech Stack:** Vite, React, TypeScript strict, Tailwind CSS v4, shadcn/ui, react-router, Recharts, `@mediapipe/tasks-vision`, vitest, Playwright, pnpm.

**Read first:**
- `PRD.md` (sections 5 and 6, the check flow and the frontend requirements)
- `CLAUDE.md` (project rules)
- **The API contract, `docs/contracts.md`.** It lands on `main` about 1.5 h in; until then, use the Interfaces blocks below.

`CLAUDE.md` also points to a design spec under `docs/superpowers/`. You don't have that file, and you don't need it: everything the frontend needs is in this plan, the PRD, and the contract.

## Who does what

- **You (frontend):** everything under `frontend/`, plus `docs/frontend.md` and this file (`docs/frontend-plan.md`, so you can tick boxes), on branch `track/frontend`. You never edit any other file.
- **Your partner (backend):**
  - the backend, the board hardware, the analysis code;
  - `docs/contracts.md`;
  - the root files (`Makefile`, `.gitignore`, `CLAUDE.md`);
  - merging both branches into `main` at the merge points below.
- **Contract changes:** if you need a field, endpoint or message that isn't in `docs/contracts.md`, ask your partner. They update the contract on `main`, then you pull `main` and update `types.ts` and the fixtures to match.

## How you work without the backend

- **Before the backend exists:** fixture mode. `VITE_USE_FIXTURES=1 pnpm dev` serves every REST call from `src/api/fixtures/*.json` and replays `src/api/fixtures/ws_stream.json` as the WebSocket.
- **After merge point I1** (about 8 h in): pull `main` and run the real backend on the simulator with `make dev` from the repo root. That needs `uv` (`brew install uv`); the Makefile starts both servers. The dev panel (`/dev`) drives the simulator: tremor Hz, amplitude, noise, hand height, and "Trigger descent".
- **You never need the board.** Every hardware-dependent behavior has a simulator equivalent. The tap test uses your own laptop camera.

## What your partner needs from you, and when

| Merge point | ~Time | Frontend tasks that must be done | What gets checked together |
|---|---|---|---|
| **I1** | 8 h | F0, F1, 4, 12 | Changing the simulator's tremor Hz visibly changes the waveform, and a 5 Hz peak is shown in the Rest step, against the real backend |
| I2 | 12 h | None (hardware only) | — |
| **I3** | 15 h | 21, 22, 23 | Full check click-through on the simulator, then on real hardware |
| **I4** | 20 h | 26 | Seeded dashboard shows the wearing-off rise and the caffeine effect |
| **I5** | 23 h | 27F, 28F, 29F | Demo rehearsal works without hardware |

At each merge point:
1. Run `pnpm test && pnpm typecheck && pnpm lint && pnpm build`.
2. Commit to `track/frontend` and tell your partner.
3. After they merge, pull `main` and fix any field-name drift against the real API.

## Global Constraints

- **AI agents never run `git add`, `git commit` or `git push`** (CLAUDE.md rule 4). You commit your own branch.
- Only edit `frontend/**`, `docs/frontend.md` and `docs/frontend-plan.md`.
- Dependencies:
  - Runtime: `react`, `react-dom`, `react-router`, `recharts`, `@mediapipe/tasks-vision`, `tailwindcss` v4 with `@tailwindcss/vite`, and what shadcn/ui installs.
  - Dev: `vitest`, `@playwright/test`, plus the Vite TS template's own tooling.
  - **Ask before adding anything else.**
- Served only from `http://localhost:5173`, which the browser treats as a secure origin, so the camera works. API base: `import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'`.
- TS mirror types use the backend's **snake_case** field names exactly, as written in `docs/contracts.md`.
- **Streaming data** (IMU, ToF, spectrum) lives in refs and is drawn on `<canvas>` in `requestAnimationFrame` loops. **Never put it in React state per sample.** Only low-rate values (connection, status, position) go in state.
- All user-facing strings live in `src/copy.ts`.
  - Footer, exactly: `Tremor Lab is a tracking tool, not a medical device. Discuss results with your doctor.`
  - Banned pattern, enforced by a vitest test: `/diagnos|you have|(increase|decrease|change) (your )?(dose|medication)/i`.
  - Plain, friendly language. Never label a condition or give medical advice.
- No runtime network calls outside localhost. The MediaPipe model and WASM are served from `public/mediapipe/`.
- TS strict, no `any`. Components are PascalCase files (`Waveform.tsx`); hooks and modules are camelCase (`useSensorStream.ts`). One component per file.
- Code comments are at most one line, with no plan identifiers (Task 12, I3, §6).
- **Charts:**
  - one small palette defined as CSS variables, readable in light and dark;
  - axes labeled with units;
  - every bin or bar shows its sample count `n`;
  - no 3-D, no pie charts;
  - tooltips show exact values.

## Review Focus

1. **Browser reload on `/check/:checkId` mid-check.** Expected: the runner calls `GET /api/checks/:id` and resumes at the first test that isn't `done`. If every test is done, it goes to Results. Test: Task 21, `resumeStep`.
2. **WebSocket drops or the backend restarts mid-test.** Expected: `useSensorStream` reconnects with backoff 0.5 s doubling to 5 s, and the step pauses with the disconnect message instead of freezing. Test: Task 23, `nextBackoff`.
3. **`POST /api/checks/:id/tests` returns 409 `test_active`** (a stale recording from another tab). Expected: friendly copy plus Retry, never an unhandled rejection. Test: Task 23, add `test_active` to `failReasonCopy`.
4. **Camera denied, or no hand visible for more than 1 s.** Expected: the instructions or the "Move your hand into the light" prompt, with Skip, and the flow continues. Covered by Task 22.
5. **Fixture shapes drift from the real API.** Expected: caught at I1, I3 and I4 by running against the real backend. Keep the fixtures generated from `docs/contracts.md`, never hand-edited to make a screen work.

---

### Task F0: Scaffold + design system (start immediately, no backend needed)

**Files:**
- Create:
  - `frontend/` from `pnpm create vite frontend --template react-ts`
  - `src/main.tsx` (router)
  - `src/App.tsx` (layout, nav, footer)
  - `src/copy.ts`
  - `src/copy.test.ts`
  - placeholder screens `src/screens/{Home,CheckIn,TestRunner,Results,Dashboard,Report,Settings,DevPanel}.tsx`

**Interfaces:**
- Produces:
  - Routes: `/`, `/check-in`, `/check/:checkId`, `/results/:checkId`, `/dashboard`, `/report`, `/settings`, `/dev`.
  - `copy` object with `copy.footer`.
  - Package scripts: `dev`, `build`, `test` (`vitest run`), `typecheck` (`tsc -b --noEmit`), `lint`, `test:e2e`.

- [ ] **Step 1: Scaffold.**
  - Run `pnpm create vite frontend --template react-ts`.
  - Run `pnpm add react-router recharts @mediapipe/tasks-vision`.
  - Install Tailwind v4 via `@tailwindcss/vite`.
  - Run `pnpm dlx shadcn@latest init`, then add `button card badge slider`.
  - Run `pnpm add -D vitest @playwright/test` and `pnpm exec playwright install chromium`.
- [ ] **Step 2: Pick the visual direction.**
  - Choose a calm, high-contrast, large-touch-target look for older users with hand tremor: 56 px+ buttons, 18 px+ body text, generous spacing, and one accent color.
  - Put the tokens in the shadcn CSS variables.
- [ ] **Step 3: Write failing vitest tests.**
  ```ts
  test('copy has no banned phrases', () => {
    expect(JSON.stringify(copy)).not.toMatch(/diagnos|you have|(increase|decrease|change) (your )?(dose|medication)/i)
  })
  test('footer text is exact', () => expect(copy.footer).toBe('Tremor Lab is a tracking tool, not a medical device. Discuss results with your doctor.'))
  ```
- [ ] **Step 4: Implement** the router, layout, footer and placeholder screens.
- [ ] **Step 5: Run the gates.** `pnpm test && pnpm typecheck && pnpm lint && pnpm build`. Expected: PASS.
- [ ] **Step 6: Checkpoint.** Commit to `track/frontend`.

### Task F1: Types, API client, fixtures (after `docs/contracts.md` lands on `main`)

**Files:**
- Create:
  - `src/api/types.ts`
  - `src/api/client.ts`
  - `src/api/fixtures/*.json`
  - `src/api/fixtures/ws_stream.json`
  - `src/api/client.test.ts`

**Interfaces:**
- Consumes: `docs/contracts.md`. Pull `main` first.
- Produces:
  - `types.ts`: one TS type per REST request/response and per WebSocket message in the contract. Names match the Pydantic names: `Health`, `SimParams`, `CheckInRequest`, `CheckCreated`, `StartTestRequest`, `TestStarted`, `ResultOut`, `TestOutcome`, `CheckOut`, `TestOut`, `CardOut`, `CheckSummaryOut`, `DoseOut`, `Bin`, `FactorEffect`, `ProfileRow`, `DayPoint`, `InsightsSummary`, `ReportOut`, `SettingsModel`, `ImuMsg`, `TofMsg`, `SpectrumMsg`, `PositionMsg`, `StatusMsg`, `SourceMsg`, `ErrorOut`, plus the `TestType`, `Hand`, `LedCommand` and `FailReason` unions.
  - `client.ts`:
    - `API_BASE`
    - `USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1'`
    - `class ApiError extends Error { status: number; error: string }`
    - `request<T>(path: string, init?: RequestInit): Promise<T>`. In fixture mode it resolves `fixtures/<key>.json`; the key comes from a method + path table in `client.ts`.
  - Endpoint functions are added by the tasks that need them (4, 12, 21, 22, 26, 27F, 28F, 29F).
  - `ws_stream.json`: about 3 s of `imu`, `tof`, `spectrum`, `status` and `source` messages for a 5 Hz tremor. Your partner can dump it from the simulator with one command once the backend exists. Until then, generate it with a small Node script: a 5 Hz sine plus gravity on z.

- [ ] **Step 1: Write failing vitest tests.**
  - `request` throws `ApiError` with `status` and `error` on a non-2xx (mock `fetch`).
  - In fixture mode, `request('/api/health')` returns the fixture.
- [ ] **Step 2: Implement.** Write one fixture per response shape in the contract.
- [ ] **Step 3: Run the gates.** Expected: PASS.
- [ ] **Step 4: Checkpoint.**

### Task 4: Frontend scaffold with a live waveform and dev panel (needed for I1)

**Files:**
- Create `frontend/` with pnpm, from the Vite `react-ts` template, then add:
  - `src/main.tsx` (router)
  - `src/App.tsx` (layout + footer)
  - `src/copy.ts`
  - `src/copy.test.ts`
  - `src/api/client.ts`
  - `src/api/useSensorStream.ts`
  - `src/viz/ringbuf.ts`
  - `src/viz/ringbuf.test.ts`
  - `src/viz/Waveform.tsx`
  - `src/screens/Home.tsx`
  - `src/screens/DevPanel.tsx`
  - `e2e/smoke.spec.ts`
  - `playwright.config.ts`
- Modify: none outside `frontend/`.

**Interfaces:**
- Consumes: `WS /ws` messages, `GET /api/health`, `GET` and `PUT /api/sim`.
- Produces:
  - `api/types.ts` (from Task F1) holds TS mirrors of the WebSocket messages (`ImuMsg`, `TofMsg`, `SpectrumMsg`, `PositionMsg`, `StatusMsg`, `SourceMsg`), plus `Health` and `SimParams`. Field names match the backend exactly (snake_case).
  - `api/client.ts`:
    - `API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'`
    - `getHealth(): Promise<Health>`, `getSim()`, `putSim(p: Partial<SimParams> | {action: 'descent'})`
    - A shared `request<T>(path, init)` that throws `ApiError {status, error, message}`.
  - `viz/ringbuf.ts`: `class RingBuf { constructor(capacity: number, width: number); push(t: number, row: number[]): void; forEach(fn); size; last(): ...; clear() }`.
  - `api/useSensorStream()` returns:
    ```ts
    { imu: RefObject<RingBuf>, tof: RefObject<RingBuf>, spectrum: RefObject<SpectrumMsg | null>,
      position: PositionMsg | null, status: StatusMsg | null, source: SourceMsg | null, connected: boolean }
    ```
    - Only the low-rate values (`position`, `status`, `source`, `connected`) are React state.
    - Reconnects with backoff 0.5 s → 5 s.
    - IMU sample times are rebuilt from `t0 + i/fs`.
  - `viz/Waveform.tsx`: `<Waveform buf={RefObject<RingBuf>} channel={0..5} seconds={5} />`. Canvas, `requestAnimationFrame`, auto-scales y.
  - `copy.ts` exports the `copy` object, including `copy.footer` (exact text from Global Constraints).

- [ ] **Step 1: Scaffold. Task F0 already did this, so skip it.** For reference, the commands it used: `pnpm create vite frontend --template react-ts`, then:
  - `pnpm add react-router recharts`
  - Tailwind v4 via `@tailwindcss/vite`
  - `pnpm dlx shadcn@latest init` (neutral theme), then add `button card badge slider`
  - `pnpm add -D vitest @playwright/test`
  - Add scripts: `test` (vitest run), `typecheck` (`tsc -b --noEmit`), `test:e2e`.
- [ ] **Step 2: Write failing vitest tests.**
  ```ts
  test('copy has no banned phrases', () => {
    const text = JSON.stringify(copy)
    expect(text).not.toMatch(/diagnos|you have|(increase|decrease|change) (your )?(dose|medication)/i)
  })
  test('footer text is exact', () => expect(copy.footer).toBe('Tremor Lab is a tracking tool, not a medical device. Discuss results with your doctor.'))
  test('ringbuf keeps last N', () => { /* push 15 into capacity 10 → size 10, first t is 5 */ })
  ```
- [ ] **Step 3: Run the tests.** `pnpm test`. Expected: FAIL.
- [ ] **Step 4: Implement the modules above.**
  - `Home` shows a status chip from `getHealth()` and the `source` message, a `<Waveform channel={0}>`, and the footer.
  - `DevPanel` (route `/dev`) is rendered only when `import.meta.env.DEV && health.sensor_source === 'sim'`. It has sliders for tremor Hz (2–12), amplitude (0–1.5), noise (0–0.2) and hand height (50–400 mm), plus a "Trigger descent" button. Each calls `putSim`.
- [ ] **Step 5: Write the Playwright smoke test (`e2e/smoke.spec.ts`).**
  - Runs against the real backend in simulator mode, so you can only run it from I1 on (`make dev` from the repo root). Before I1, check the waveform by eye in fixture mode.
  - Loads `/` and waits 1.5 s.
  - Asserts the waveform canvas has more than 50 non-background pixels.
  - Calls `PUT /api/sim {tremor_hz: 2}` and screenshots the canvas, then `{tremor_hz: 10}` and screenshots again.
  - Asserts the two images differ, by counting zero-crossings in the canvas pixel column profile. This is the M0 acceptance check.
- [ ] **Step 6: Run the gates.**
  - Now: `pnpm test && pnpm typecheck && pnpm lint && pnpm build`.
  - From I1 on: also `make dev` in the background, then `pnpm test:e2e`.
  - Expected: all pass.
- [ ] **Step 7: Checkpoint (ready for I1).** Commit and tell your partner.
  - At I1, verify together: change `SIM_TREMOR_HZ` (env var + restart, or the dev panel slider) and see the waveform change.

### Task 12: Rest step UI with live spectrum (needed for I1)

**Files:**
- Create:
  - `frontend/src/viz/Spectrum.tsx`
  - `frontend/src/flow/checkFlow.ts`
  - `frontend/src/flow/checkFlow.test.ts`
  - `frontend/src/screens/TestRunner.tsx`
  - `frontend/src/screens/steps/RestStep.tsx`
  - `frontend/src/components/StepPills.tsx`
  - `frontend/src/components/Countdown.tsx`
- Modify:
  - `frontend/src/api/client.ts` (add `createCheck`, `startTest`, `stopTest`, `markTest`)
  - `frontend/src/copy.ts` (rest instructions)
  - `frontend/src/main.tsx` (route `/check/:checkId`)
  - `frontend/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: `POST /api/checks`, `POST /api/checks/{id}/tests`, `POST /api/tests/{id}/stop`, `POST /api/tests/{id}/mark` (shapes in `docs/contracts.md`), and `useSensorStream().spectrum`.
- Produces:
  - `checkFlow.ts`:
    - `type Step = 'rest' | 'posture' | 'reach' | 'tap-left' | 'tap-right' | 'results'`
    - `type Phase = 'intro' | 'recording' | 'paused' | 'analyzing' | 'result' | 'failed'`
    - `type FlowState = { step: Step; phase: Phase; attempt: number; outcomes: Partial<Record<Step, TestOutcome>> }`
    - `type FlowEvent = {type: 'begin'} | {type: 'pause'} | {type: 'resume'} | {type: 'stopped', outcome} | {type: 'retry'} | {type: 'skip'} | {type: 'next'} | {type: 'attemptDone'}`
    - `reduce(s: FlowState, e: FlowEvent): FlowState`
    - `initialFlow: FlowState`
    - Order: rest → posture → reach (attempts 1..3) → tap-left → tap-right → results. `skip` records the step as `{status: 'failed', fail_reason: 'skipped'}`.
  - `<Spectrum spec={RefObject<SpectrumMsg | null>} maxHz={15} />`:
    - Canvas.
    - Shades the 3–12 Hz band and marks the peak with a `"{peak_hz.toFixed(1)} Hz"` label.
    - Shows `copy.noClearTremor` when `peak_hz` is null.
  - `RestStep({checkId, onOutcome})`:
    1. On begin, calls `startTest(checkId, 'rest', hand)`.
    2. Runs a 30 s `Countdown`.
    3. Calls `stopTest`.
    4. Shows the peak Hz and score.
    - Hand comes from settings, defaulting to `'right'` until Task 28F.

- [ ] **Step 1: Write failing vitest tests** for `reduce`: the full happy path sequence, three reach attempts before moving to tap, retry resetting the phase to intro, skip recording a failed outcome, and pause/resume only from recording.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Home's "Start check" button: temporarily `createCheck({medication: 'not_yet'})`, then navigate to `/check/:id`. Task 21 replaces it with the check-in screen.
  - The TestRunner renders the step component for `state.step`. Only `rest` exists so far; the other steps show "coming soon" and Skip.
- [ ] **Step 4: Extend the Playwright smoke test.** Set sim to 5 Hz, start a check, begin rest, wait 12 s, and assert the spectrum label matches `/^(4\.[89]|5\.[0-2]) Hz$/`.
- [ ] **Step 5: Run the gates.** `pnpm test && pnpm typecheck && pnpm lint && pnpm build`. Add `pnpm test:e2e` from I1 on. Expected: PASS.
- [ ] **Step 6: Checkpoint (ready for I1).** At I1, verify together that simulated 5 Hz shows a 5.0 Hz peak in the Rest step.

### Task 21: Check-in, posture, reach and results screens

**Files:**
- Create:
  - `frontend/src/screens/CheckIn.tsx`
  - `frontend/src/screens/steps/PostureStep.tsx`
  - `frontend/src/screens/steps/ReachStep.tsx`
  - `frontend/src/screens/Results.tsx`
  - `frontend/src/viz/ReachCurve.tsx`
  - `frontend/src/viz/HeightGuide.tsx`
- Modify:
  - `frontend/src/screens/TestRunner.tsx`
  - `frontend/src/screens/Home.tsx` ("Start check" now goes to `/check-in`)
  - `frontend/src/api/client.ts` (add `getCheck`, `listChecks`)
  - `frontend/src/copy.ts`
  - `frontend/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: `CheckInRequest`, `CheckSummaryOut`, the `position` and `status` WebSocket messages, `markTest`.
- Produces:
  - **CheckIn:**
    - Large buttons: Now / 30 min ago / 1 h / 2 h / 3 h / 4 h+ / Not yet.
    - Optional chips: caffeine yes/no, sleep 1–5, stress 1–5, alcohol yes/no.
    - Calls `createCheck`, then goes to `/check/:id`.
  - **PostureStep:**
    - Starts the test.
    - The countdown runs only while `position.in_band`. When out of band, it dispatches `pause` and shows `copy.raiseHand` if `tof_mm < band_lo`, else `copy.lowerHand`.
    - Shows `<HeightGuide position={...}/>`, plus the same waveform and spectrum as the rest step.
    - Stops when 30 s of in-band time has accumulated, or after a 60 s hard limit.
  - **ReachStep:**
    - Starts one test, runs 3 attempts of up to 8 s each, and calls `markTest` between attempts.
    - `<ReachCurve tof={RefObject<RingBuf>} />` draws the live descent. After stop, the final 50 mm are colored amber when `wobble_ratio > 1.5`.
    - On sim, the dev panel's "Trigger descent" drives it.
  - **Results:**
    - `GET /api/checks/:id` drives four cards. Each shows the value, then either `+x% vs your usual` or `copy.buildingBaseline`.
    - Shows `minutes_since_dose` formatted as "2 h 10 min since last dose".
    - Failed or skipped cards show `copy.notRecorded`.

- [ ] **Step 1: Extend the vitest tests.**
  - `resumeStep(summary: CheckSummaryOut): Step`: returns the first step whose test isn't `done`, or `'results'`. TestRunner calls it on mount.
  - The `reduce` posture pause/resume path.
  - A `formatSinceDose` helper: 130 gives "2 h 10 min", null gives `copy.noDoseLogged`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Extend the Playwright smoke test.** It runs against the real simulator, so it only passes after I3; in fixture mode, click through by hand. On sim, click through check-in → rest (wait) → posture (sim hand stays in band) → reach (call `PUT /api/sim {action: 'descent'}` per attempt) → skip both taps → Results shows 4 cards (2 tap cards "Not recorded").
- [ ] **Step 5: Run the gates.** Expected: PASS.
- [ ] **Step 6: Checkpoint.**

### Task 22: Tap step with MediaPipe

**Files:**
- Create:
  - `frontend/src/screens/steps/TapStep.tsx`
  - `frontend/src/tap/handLandmarker.ts`
  - `frontend/src/tap/tapCounter.ts`
  - `frontend/src/tap/tapCounter.test.ts`
  - `frontend/src/viz/HandOverlay.tsx`
  - `frontend/scripts/fetch_mediapipe.sh`
  - `docs/frontend.md` (MediaPipe setup)
- Modify: `frontend/package.json` (`postinstall` copies the WASM files), `frontend/src/api/client.ts` (`postTapData`), `frontend/src/copy.ts`

**Interfaces:**
- Consumes: `POST /api/tests/{id}/tap-data`.
- Produces:
  - `frontend/scripts/fetch_mediapipe.sh`:
    - Copies `node_modules/@mediapipe/tasks-vision/wasm/*` to `frontend/public/mediapipe/wasm/`.
    - Downloads `hand_landmarker.task` once to `frontend/public/mediapipe/hand_landmarker.task` (a setup-time download, not at runtime).
    - Both outputs are gitignored. `.gitignore` already lists `frontend/public/mediapipe/`.
  - `createHandLandmarker(): Promise<HandLandmarker>`: VIDEO mode, `numHands: 1`, local paths only.
  - `tapCounter.ts`: `class LiveTapCounter { push(t: number, ratio: number): number /* returns count */; reset() }`. A simple hysteresis counter (rise above 0.5, then fall below 0.25) used only for the on-screen counter. The backend is authoritative.
  - **TapStep({checkId, hand}):**
    - `getUserMedia` for video.
    - A per-frame rAF loop runs `detectForVideo` and pushes `{t_ms, lm: [[x, y] for 0, 4, 8, 9] | null}`.
    - `HandOverlay` draws thumb and index points with a connecting line.
    - Shows `copy.moveIntoLight` after more than 1 s with no hand.
    - Gives a 3 s get-ready, then records for 10 s, then calls `postTapData`.
    - Camera denied: shows `copy.cameraDenied` plus Skip.

- [ ] **Step 1: Write failing vitest tests** for `LiveTapCounter`: a synthetic 4 Hz ratio series over 10 s gives 40 ± 2, and noise below the hysteresis gives 0.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: HUMAN ACTION REQUIRED, camera check.**
  1. Run `pnpm dev` (fixture mode works; use the real backend after I1) and open http://localhost:5173.
  2. Run a check through to the tap step and allow the camera.
  3. Tap for 10 s with each hand.
  4. Success signal: landmarks overlay your fingers, the live counter increases, and the Results tap card shows a taps/s value.
- [ ] **Step 5: Run the gates.** Expected: PASS.
- [ ] **Step 6: Checkpoint.**

### Task 23: Disconnect and backend-down error states (needed for I3)

**Files:**
- Create: `frontend/src/components/ConnectionBanner.tsx`, `frontend/src/components/SourceChip.tsx`
- Modify:
  - `frontend/src/screens/TestRunner.tsx`
  - All the step components (pause on `source.connected === false`, then show the retry UI)
  - `frontend/src/screens/Home.tsx`
  - `frontend/src/copy.ts`

**Interfaces:**
- Consumes: the `source` WebSocket message, `ApiError`, `TestOutcome.fail_reason`.
- Produces:
  - `ConnectionBanner` shows `copy.backendDown` when `/api/health` fails twice in a row (polled every 3 s).
  - `SourceChip` shows green Connected, amber Simulator / Replay, or red "Sensor disconnected — check the USB cable". It also names any missing sensor.
  - Every `fail_reason` maps to friendly copy, with Retry and Skip:
    - `insufficient_valid_data`
    - `no_descent_detected`
    - `no_taps_detected`
    - `sensor_disconnected`
    - `interrupted`

- [ ] **Step 1: Write failing vitest tests.**
  - `nextBackoff(ms)`: 500 → 1000 → … → 5000, capped at 5000. Used by `useSensorStream`.
  - `failReasonCopy` also covers `test_active`. `failReasonCopy` must have an entry for each of those reasons, and none of them may match the banned pattern.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run the gates.** Expected: PASS.
- [ ] **Step 4: At I3, with your partner (they have the board): end-to-end on hardware.**
  1. Run `make dev SENSOR_SOURCE=board`, then complete a full check.
  2. Mid-rest, unplug the USB cable. The UI should show the disconnect message and a Retry button. Re-plug it and run `make board-link`; Retry should then work.
  3. Then run `sqlite3 backend/data/tremorlab.db "select type,status from tests order by id desc limit 6"`. All 6 should be `done`.
- [ ] **Step 5: Checkpoint (ready for I3).** Commit and tell your partner.

### Task 26: Dashboard screen (needed for I4)

**Files:**
- Create:
  - `frontend/src/screens/Dashboard.tsx`
  - `frontend/src/charts/DoseResponseChart.tsx`
  - `frontend/src/charts/DailyTimeline.tsx`
  - `frontend/src/charts/ProfileChart.tsx`
  - `frontend/src/charts/FactorBars.tsx`
  - `frontend/src/components/RecentChecks.tsx`
- Modify:
  - `frontend/src/api/client.ts`
  - `frontend/src/main.tsx` (`/dashboard`)
  - `frontend/src/screens/Home.tsx` (streak, link to the dashboard)
  - `frontend/src/copy.ts`
  - `frontend/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: `GET /api/insights/dose-response`, `GET /api/insights/factors`, `GET /api/insights/profile`, `GET /api/insights/summary`, `GET /api/checks` (shapes in `docs/contracts.md`).
- Produces:
  - Metric cards: checks completed, "Tremor typically returns about X h after a dose" (hidden when null), and the largest factor effect phrased neutrally (e.g. "Caffeine days: 18% higher tremor (n=21 vs 23)").
  - Dose-response chart:
    - Recharts `ComposedChart`: bars for the mean, labeled by count.
    - x is hours since dose (0–6). Vertical reference lines at 0 and at the median dose interval.
  - Daily timeline: mean rest per day as a line, with dose times as markers.
  - Movement profile: a bar pair (first week vs current) for each of the 4 tests, with n shown.
  - Recent checks: the last 10, linking to the Results view.
  - `copy.footer` at the bottom.
  - Charts follow the chart rules in Global Constraints.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Extend the Playwright smoke test.** After `make seed`, `/dashboard` renders 4 charts. The "returns after" card text matches `/about [2-4](\.\d)? h/`.
- [ ] **Step 3: Run the gates.** `pnpm test && pnpm typecheck && pnpm lint && pnpm build && pnpm test:e2e`. Expected: PASS. Your partner runs `make seed` first.
- [ ] **Step 4: Checkpoint (ready for I4).** At I4, verify together that the seeded data shows the wearing-off rise and the caffeine effect.

### Task 27F: Doctor report screen

**Files:**
- Create: `src/screens/Report.tsx`, `src/styles/print.css`
- Modify: `src/api/client.ts` (`getReport(days)`), `src/copy.ts`

**Interfaces:**
- Consumes: `GET /api/report?days=14`, which returns `ReportOut {period: {start, end}, checks_completed, dose_response, returns_after_h, factors, profile, daily, generated_at}`.
- Produces: `/report`, a one-page layout. **Every insight shows `n=`.** It has a Print button (`window.print()`). `@media print` hides the nav and buttons. `copy.footer` is at the bottom. It reuses the Task 26 chart components where they fit.

- [ ] **Step 1: Implement.** Use a `report.json` fixture until I4.
- [ ] **Step 2: Run the gates.** Expected: PASS. Print-preview manually: it fits on one Letter page.
- [ ] **Step 3: Checkpoint.**


### Task 28F: Settings screen

**Files:**
- Create: `src/screens/Settings.tsx`, `src/api/useSettings.ts`
- Modify: `src/screens/Home.tsx`, `src/screens/steps/RestStep.tsx`, `src/screens/steps/PostureStep.tsx`, `src/api/client.ts`

**Interfaces:**
- Consumes: `GET/PUT /api/settings`, which takes and returns `SettingsModel {dose_times: string[] "HH:MM", reminder_times: string[], tested_hand: 'left'|'right', posture_band: [number, number] | null}`.
- Produces:
  - `useSettings(): {settings: SettingsModel | null, save(p: Partial<SettingsModel>): Promise<void>}`
  - Home's "Next check" is the next `reminder_times` entry, falling back to the next dose time plus 1 h.
  - Rest and Posture use `tested_hand` instead of the `'right'` default.

- [ ] **Step 1: Write a failing vitest test** for `nextCheckTime(settings, now)`: reminder preferred, dose plus 1 h fallback, wraps to tomorrow.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run the gates.** Expected: PASS.
- [ ] **Step 4: Checkpoint.**


### Task 29F: LED cues + demo doc (M5)

**Files:**
- Create: `src/api/led.ts`
- Modify: the step components, `src/screens/TestRunner.tsx`, `src/screens/Home.tsx`

**Interfaces:**
- Consumes: `POST /api/led {command, value?}`. On the simulator it's a no-op, so you can build this without the board.
- Produces:
  - `cue(command: LedCommand, value?: number): void` is fire-and-forget and swallows errors.
  - Cue map:

    | Moment | LED command |
    |---|---|
    | Test intro | `hold` |
    | Recording starts | `recording 1` |
    | Each second | `countdown n` |
    | Out of band | `hold` |
    | Result | `check`, then `recording 0` |
    | Home mount | `idle` |

- [ ] **Step 1: Write a failing vitest test.** With `fetch` mocked to reject, `cue` never throws.
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run the gates.** Expected: PASS.
- [ ] **Step 4: Rehearse with your partner.** Join the demo rehearsal at I5. Your partner writes `docs/demo.md`.
- [ ] **Step 5: Checkpoint.**

