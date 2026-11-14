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

## Remaining work

This is the frontend portion of the initial scaffold milestone, not the full application. The repository has no backend, Makefile, or `docs/contracts.md`; backend integration is unverified. Types and simulator field names are provisional based on the supplied plan. Align them with the partner's contract before integration. Synthetic fixture generation is currently in the streaming hook rather than contract-derived JSON.

The check flow, spectrum, posture/reach gating, MediaPipe tap recording, persisted results, dashboard, printable report, and settings are subsequent milestones. Their routes show explicit development placeholders. The check-in route previews the routine; it does not create or record a check. Recharts and MediaPipe are installed but not loaded. Shared styling uses Tailwind v4 and custom CSS; shadcn component extraction and remaining design-system work are outstanding. No cloud publication or repository commits were performed.
