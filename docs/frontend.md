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
| Home trends, dashboard | Sample data, labeled as such | `/api/insights/*` and `GET /api/checks?details=false` |
| Settings | Saved in the browser | `GET/PUT /api/settings` (the hand also syncs from the Settings dialog) |
| Report | Placeholder | `GET /api/report` |

The Playwright suite runs in fixture mode, so it needs no backend.

### Sensor mode check flow

1. **Connect:** `GET /api/health` reports the board link and both sensors. The medication question then creates the check (`POST /api/checks`). Its choices are Just now, 30 min, 1–4 h and Not yet; they map to `now`, `hours_ago` and `not_yet`. The tested hand comes from `/api/settings`.
2. **Rest:** a 30 s recording on the wall clock.
3. **Posture:** runs until there are 30 s of in-band time, taken from `position.valid_seconds`. It gives up after 75 s, and the backend needs at least 20 s.
4. **Reach:** a single recording. The app sends `POST /api/tests/{id}/mark` before attempts 2 and 3. On the simulator, each attempt also sends `PUT /api/sim {"action": "descent"}`.
5. **Tap:** allow camera access, then record the left and right hand for 10 seconds each after a 3-second countdown. MediaPipe runs locally and sends landmarks to the existing tap-data endpoint. Retry failed recordings or skip the step; successful hands are saved independently.
6. **Results:** `/results/:checkId` reads `GET /api/checks/{id}`.

Every test step stops on a link drop (a `source` message with `connected: false`). A failed test shows friendly copy for its `fail_reason` with a Try again button, and any test step can be skipped. LED cues follow the map in `docs/demo.md` and are best effort.

Code map:
- `src/api/types.ts` mirrors `docs/contracts.md`. `src/api/wsMessages.ts` validates every `/ws` frame.
- `src/api/useSensorStream.ts` keeps samples in refs: IMU, ToF, spectrum and position. Only the link state is React state.
- `src/check/useLiveTest.ts` handles test timing.
- `src/check/LiveCheckPage.tsx` holds the sensor-mode test steps. The connect step stays in `CheckPage.tsx` for both modes.
- `src/dashboard/`, `src/results/`, `src/report/` and `src/settings/` are the data screens.

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
tap tests with an empty frame submission. Completed left-hand progress survives
refresh before recording the right hand. The UI tap counter is feedback only.

Manual hardware check: start a sensor check, reach Tap, allow the camera, and
record each hand. Confirm the landmark overlay, tap counter, and backend result.
Browser automation checks camera lifecycle and request contracts, but cannot
validate tracking accuracy on a person's hand.
