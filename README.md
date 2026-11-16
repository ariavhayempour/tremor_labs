# Tremor Lab

An at-home 2-minute movement check (rest, posture, reach, tap) for people already diagnosed
with a tremor condition. Each check records one hand, and results are logged next to
medication times so patients, caregivers and neurologists can see when tremor changes and
compare hands. It is a tracking tool, not a medical device.

An Arduino UNO Q samples the sensors over USB-C and runs the sensor signal analysis on the
board. Everything else runs locally on the Mac: a FastAPI backend (`localhost:8000`) that
stores results in SQLite, and a Vite + React frontend (`localhost:5173`) with the MediaPipe
tap test. If the board stops answering, the Mac runs the same analysis code itself. How it
fits together: [`docs/technical-overview.md`](docs/technical-overview.md).

## First-time setup

```bash
brew install uv pnpm
cd backend && uv sync
cd ../frontend && pnpm install
```

For the board, install Arduino App Lab as well. It bundles its own `adb`, which `make` and
`make doctor` find on their own. `brew install android-platform-tools` also works.

## Run with the simulator (no board)

```bash
make dev
```

Then open `http://localhost:5173`.

## Run with the board

**HUMAN ACTION REQUIRED:** plug the UNO Q into the Mac over USB-C and quit App Lab (it holds
the `adb` connection). Run every command from the repo root.

**First time on a board only:** push the whole app once so the sketch is on it:

```bash
adb push board/tremorlab /home/arduino/ArduinoApps/
```

If `adb` isn't on your `PATH`, use App Lab's copy:
`~/Library/Arduino15/packages/arduino/tools/adb/<version>/adb`.

**Terminal 1**: deploy the analysis code to the board, then start the backend and frontend:

```bash
make board-deploy
make dev SENSOR_SOURCE=board
```

- `make board-deploy` copies `backend/tremorlab/analysis/` and vendored NumPy/SciPy into the
  app, pushes it and restarts it. The first run downloads the two wheels once. Run it again
  after any change to `analysis/` or `board/tremorlab/python/`.
- If the `stop` step prints an error, ignore it; it just means the app wasn't running yet.
- Before `make dev` starts you should see `✓ App "tremorlab" started successfully`.

**Terminal 2**: once Terminal 1 shows the backend and frontend running:

```bash
make doctor
open -a "Google Chrome" http://localhost:5173
```

Every line of `make doctor` should say `PASS`, ending with `analysis`, which shows the board is
doing the signal processing. If any line fails, follow its hint. If it still fails, unplug the
board, wait 5 seconds, plug it back in, wait about 40 seconds and run Terminal 1 again.

## Common commands

| Command | What it does |
|---|---|
| `make dev` | Backend + frontend on the simulator |
| `make dev SENSOR_SOURCE=board` | Same, reading the real board (runs `make board-link` first) |
| `make dev SENSOR_SOURCE=replay` | Same, replaying a stored check |
| `make board-link` | `adb forward` of tcp:7700 (sample stream) and tcp:7701 (analysis server) |
| `make board-deploy` | Copy the analysis code and NumPy/SciPy to the board app and restart it |
| `make seed` | 14 days of deterministic demo data (replaces the local DB) |
| `make demo` | Rehearsal mode: replay source + seeded DB |
| `make test` / `make test-e2e` | pytest + vitest / Playwright smoke |
| `make lint` / `make typecheck` / `make build` | Quality gates |
| `make doctor` / `make rate` | Hardware checks / measured sensor rates |
| `make dump-ws` | About 3 s of simulator `/ws` messages as JSON |

## Docs

- [`docs/technical-overview.md`](docs/technical-overview.md): architecture and design choices
- [`docs/running.md`](docs/running.md): full run guide and environment variables
- [`docs/hardware-notes.md`](docs/hardware-notes.md): board, sensors, relay and board-side analysis
- [`docs/contracts.md`](docs/contracts.md): REST / WebSocket / board wire contracts (7700 and 7701)
- [`docs/analysis.md`](docs/analysis.md): signal analysis
- [`docs/frontend.md`](docs/frontend.md) and [`docs/frontend-plan.md`](docs/frontend-plan.md): frontend notes and plan
- [`docs/demo.md`](docs/demo.md): demo script and fallbacks
- [`docs/PRD.md`](docs/PRD.md): product requirements
- [`board/README.md`](board/README.md), [`frontend/README.md`](frontend/README.md): per-folder notes
