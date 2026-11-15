# Tremor Lab

An at-home 2-minute movement check (rest, posture, reach, tap) for people already diagnosed
with a tremor condition. Results are logged next to medication times so patients, caregivers
and neurologists can see when tremor changes. It is a tracking tool, not a medical device.

Everything runs locally on the Mac: a FastAPI backend (`localhost:8000`) and a Vite + React
frontend (`localhost:5173`). An Arduino UNO Q supplies the sensor data over USB-C.

## First-time setup

```bash
brew install uv pnpm android-platform-tools
cd backend && uv sync
cd ../frontend && pnpm install
```

Install Arduino App Lab as well; it bundles its own `adb`.

## Run with the simulator (no board)

```bash
make dev
```

Then open `http://localhost:5173`.

## Run with the board

**HUMAN ACTION REQUIRED:** plug the UNO Q into the Mac over USB-C and make sure App Lab is
closed (it holds the `adb` connection). Then use two terminals, both from the repo root.

**Terminal 1**: push the board app, restart it, and start the backend and frontend:

```bash
export PATH="$HOME/Library/Arduino15/packages/arduino/tools/adb/32.0.0:$PATH"
adb push board/tremorlab /home/arduino/ArduinoApps/
adb shell 'export TMPDIR=/tmp; arduino-app-cli app stop /home/arduino/ArduinoApps/tremorlab'
adb shell 'export TMPDIR=/tmp; arduino-app-cli app start /home/arduino/ArduinoApps/tremorlab'
make dev SENSOR_SOURCE=board
```

- If the `stop` line prints an error, ignore it; it just means the app wasn't running yet.
- Before `make dev` starts you should see `✓ App "tremorlab" started successfully`.
- The `adb` version folder (`32.0.0`) may differ on your machine; check
  `ls ~/Library/Arduino15/packages/arduino/tools/adb/`. If `adb` is already on your `PATH`
  (from Homebrew), skip the `export` line.

**Terminal 2**: once Terminal 1 shows the backend and frontend running:

```bash
export PATH="$HOME/Library/Arduino15/packages/arduino/tools/adb/32.0.0:$PATH"
make doctor
open -a "Google Chrome" http://localhost:5173
```

Every line of `make doctor` should say `PASS`. If any line fails, unplug the board, wait
5 seconds, plug it back in, wait about 40 seconds and run Terminal 1 again.

## Common commands

| Command | What it does |
|---|---|
| `make dev` | Backend + frontend on the simulator |
| `make dev SENSOR_SOURCE=board` | Same, reading the real board (runs `make board-link` first) |
| `make seed` | 14 days of deterministic demo data (replaces the local DB) |
| `make demo` | Rehearsal mode: replay source + seeded DB |
| `make test` / `make test-e2e` | pytest + vitest / Playwright smoke |
| `make lint` / `make typecheck` / `make build` | Quality gates |
| `make doctor` / `make rate` | Hardware checks / measured sensor rates |

## Docs

- [`docs/running.md`](docs/running.md): full run guide and environment variables
- [`docs/hardware-notes.md`](docs/hardware-notes.md): board, sensors and relay details
- [`docs/demo.md`](docs/demo.md): demo script and fallbacks
- [`docs/contracts.md`](docs/contracts.md): REST / WebSocket / board wire contracts
- [`docs/frontend.md`](docs/frontend.md), [`docs/analysis.md`](docs/analysis.md)
- [`PRD.md`](PRD.md): product requirements
