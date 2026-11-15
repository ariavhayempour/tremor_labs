# Frontend

The first frontend milestone is implemented in `frontend/`: a responsive overview, four-step check preview, route scaffolding, canvas waveform, local simulator controls, and WebSocket reconnection with capped backoff. Streaming samples use a bounded ref-backed buffer.

## Run locally

From `frontend/`:

```sh
npx --yes pnpm install
VITE_USE_FIXTURES=1 npx --yes pnpm dev
```

Open http://localhost:5173. Fixture mode generates a clearly labeled synthetic signal locally, without recording checks. Open Simulator and change frequency or amplitude to see the waveform respond. Hand height is retained in simulator parameters for future posture/reach integration; this milestone only displays acceleration.

Without `VITE_USE_FIXTURES=1`, the app connects to `VITE_API_BASE` (default http://localhost:8000), reads `/api/health`, sends simulator settings to `/api/sim`, and consumes IMU batches from `/ws`. A dropped WebSocket reconnects after 0.5 seconds, doubling to a maximum of 5 seconds. There are no runtime CDN requests.

## Validation

```sh
npx --yes pnpm test
npx --yes pnpm typecheck
npx --yes pnpm lint
npx --yes pnpm build
npx --yes pnpm exec playwright install chromium
npx --yes pnpm test:e2e
```

Five unit tests cover copy restrictions, footer, buffer ordering/clearing, reconnection delays, and API error handling. Two browser tests cover navigation, waveform pixels, simulator changes/reset, and mobile overflow/navigation.

## Backend integration

The app has two modes. They share every screen, but the data comes from different places.

| | Fixture mode (`VITE_USE_FIXTURES=1`) | Live mode (default) |
|---|---|---|
| Check flow | "Demo mode" runs a simulated check locally and records nothing | "Sensor mode" (the default) records on the backend |
| Home trends | Sample data, labeled as such | `/api/insights/*` and `GET /api/checks?details=false` |
| Trends (`/dashboard`) | Sample data, labeled as such | Sample data, labeled as such, until it is switched to `GET /api/checks` and `GET /api/doses` (see below) |
| Settings | Saved in the browser | `GET/PUT /api/settings` (dose times, reminders and posture band; the frontend no longer reads or writes `tested_hand`) |
| Report | Placeholder | `GET /api/report` |

The Playwright suite runs in fixture mode, so it needs no backend.

### Sensor mode check flow

1. **Connect:** `GET /api/health` reports the board link and both sensors. The medication question then creates the check (`POST /api/checks`). Its choices are Just now, 30 min, 1–4 h and Not yet; they map to `now`, `hours_ago` and `not_yet`. Before that, the person picks **Left hand** or **Right hand** for this check. The choice locks once the check is created, and every test in the check is started with that `hand`. To track both hands, the person runs two checks; the summary and results pages offer "Now check your left/right hand", which opens a new check with the other hand selected.
2. **Rest:** a 30 s recording on the wall clock.
3. **Posture:** runs until there are 30 s of in-band time, taken from `position.valid_seconds`. It gives up after 75 s, and the backend needs at least 20 s.
4. **Reach:** a single recording. The app sends `POST /api/tests/{id}/mark` before attempts 2 and 3. On the simulator, each attempt also sends `PUT /api/sim {"action": "descent"}`.
5. **Tap:** allow camera access, then record the check's hand for 10 seconds after a 3-second countdown. MediaPipe runs locally and sends landmarks to the existing tap-data endpoint. Retry a failed recording or skip the step.
6. **Results:** `/results/:checkId` reads `GET /api/checks/{id}`.

Every test step stops on a link drop (a `source` message with `connected: false`). A failed test shows friendly copy for its `fail_reason` with a Try again button, and any test step can be skipped. LED cues follow the map in `docs/demo.md` and are best effort.

Code map:
- `src/api/types.ts` mirrors `docs/contracts.md`. `src/api/wsMessages.ts` validates every `/ws` frame.
- `src/api/useSensorStream.ts` keeps samples in refs: IMU, ToF, spectrum and position. Only the link state is React state.
- `src/check/useLiveTest.ts` handles test timing.
- `src/check/LiveCheckPage.tsx` holds the sensor-mode test steps. The connect step stays in `CheckPage.tsx` for both modes.
- `src/dashboard/`, `src/results/`, `src/report/` and `src/settings/` are the data screens.

### Trends screen

`/dashboard` shows a Simple tab (daily averages per test against the person's own usual range) and a Detailed tab (every check, rest tremor by time since dose, tremor rhythm, every reach and tap measure, a first-week vs last-3-days table and the raw values). Clicking a day on any chart or row opens `/dashboard/day/:date`, which has the same two tabs. `?view=detailed` and `?days=7` keep the tab and period in the URL.

- `src/trends/sampleTrends.ts` generates deterministic synthetic checks and doses in the `CheckOut` and `DoseOut` shapes, anchored to today.
- `src/trends/useTrendsData.ts` is the only data source. Switching to live data means loading `GET /api/checks` and `GET /api/doses` there and setting `sample: false` (that also turns on the "Full results" links).
- `src/trends/model.ts` holds the aggregation: daily means, the first week (the reference), the last 3 days, the usual range (interquartile range of first-week checks, shown only from 3 checks), "about the same" (within 10%), and dose bins that mirror `/api/insights/dose-response`.
- Charts use Recharts. `ChartColumns.tsx` overlays one real button per day or check on each chart, so every chart is keyboard reachable and has full-height tap targets; the tooltip is drawn by that overlay.
- `src/screens/History.tsx` and `src/dashboard/LiveHistory.tsx` (the earlier backend-driven dashboard) are no longer routed.

## Remaining work

- **Tap recording implemented:** MediaPipe landmarks 0, 4, 8, 9 are posted to `POST /api/tests/{id}/tap-data`; absent hands produce null landmarks. Video is not uploaded. The backend remains authoritative for tap metrics.
- **A live-backend Playwright run:** I1 and I3 need the smoke tests to pass against `make dev` without fixtures.
- **Error states:** a reconnect banner outside the check flow.
- **Design:** shadcn component extraction and the rest of the design-system work.

## Local MediaPipe setup

The webcam demo and model are copied into `tools/mediapipe/`. In `frontend/`,
run `npm run setup:mediapipe` to copy the model and installed package's WASM
into `public/mediapipe/` (ignored generated assets). Both `npm run dev` and
`npm run build` do this automatically. Use localhost or HTTPS for camera access.
Camera permission is requested only when starting a real tap recording; demo
mode stays simulated. Leaving the step releases the camera and closes unfinished
tap tests with an empty frame submission. The UI tap counter is feedback only.

Manual hardware check: start a sensor check, reach Tap, allow the camera, and
record the chosen hand. Confirm the landmark overlay, tap counter, and backend result.
Browser automation checks camera lifecycle and request contracts, but cannot
validate tracking accuracy on a person's hand.

### Trends: hand filter and Compare hands

Each check records a single hand: every test in it shares one `hand`, and `checkHand()` in `src/trends/model.ts` reads it from the first test.

- **Hand filter** (Both hands / Left hand / Right hand, `?hand=left|right`) applies to the Simple and Detailed views and to day pages. Choosing one hand limits the checks to that hand and recomputes the first-week reference and the last-3-days figures from that hand only. Chart scales always come from every check, so switching hands never rescales a chart. With both hands shown, tapping is drawn as separate left and right lines, and the other measures average across both hands.
- **Compare hands** (`?view=compare`) uses the selected period. It shows the left and right averages for rest, posture, reach and tapping, a daily chart of each with left and right as separate lines, and a table of every measure with "Right compared with left" (about the same within 10%). The hand filter is hidden on this tab. Day pages offer only Simple and Detailed.
- The sample data (`sampleTrends.ts`) models each sitting as a left-hand check followed by a right-hand check five minutes later.
