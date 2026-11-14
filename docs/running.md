# Running Tremor Lab

Everything runs locally on the Mac. The backend is at `http://localhost:8000`, the frontend at `http://localhost:5173`.

## Prerequisites

| Tool | Install | Used for |
|---|---|---|
| `uv` | `brew install uv` | Python 3.12 and the backend's dependencies (the system Python 3.9 is never used) |
| `pnpm` | `brew install pnpm` | Frontend dependencies |
| `adb` (board only) | `brew install android-platform-tools` | `make board-link` (USB port forward to the UNO Q) |

First time:

```bash
cd backend && uv sync          # installs Python 3.12 (pinned in backend/.python-version) and the deps
cd frontend && pnpm install    # once frontend/ exists
```

## Daily commands (repo root)

| Command | What it does |
|---|---|
| `make dev` | Backend on :8000 with `--reload`, plus the frontend on :5173 if `frontend/` exists. Uses the simulator. Ctrl-C stops both. |
| `make dev SENSOR_SOURCE=board` | Runs `make board-link` first, then reads the real board over USB. |
| `make dev SENSOR_SOURCE=replay` | Replays stored raw samples (the most recent full check, or `REPLAY_TEST_ID`). |
| `make seed` | Writes 14 days of deterministic demo data to `backend/data/tremorlab.db`. **It replaces that DB.** |
| `make demo` | Rehearsal mode: copies the seeded DB to `backend/data/demo.db`, then runs `dev` with the replay source on it. |
| `make test` / `make test-e2e` | pytest (backend) + vitest / Playwright (frontend). |
| `make lint` / `make typecheck` / `make build` | ruff / mypy, plus the frontend's lint, `tsc` and `vite build`. |
| `make doctor` / `make rate` | Hardware chain checklist / measured IMU and ToF rates. |
| `make dump-ws` | Prints about 3 s of simulator `/ws` messages as a JSON array (for `frontend/src/api/fixtures/ws_stream.json`). |

A target whose script isn't written yet fails with `scripts/<name>: file not found`.

Integration tests (`@pytest.mark.integration`, which need the real analysis) are skipped by default. Run them with `cd backend && uv run pytest -m integration`.

## Environment variables

All of them are optional. They are read by `backend/tremorlab/config.py`.

| Variable | Default | Meaning |
|---|---|---|
| `SENSOR_SOURCE` | `sim` | `sim`, `board` or `replay` |
| `SIM_TREMOR_HZ` | `5.0` | Simulated tremor frequency, Hz |
| `SIM_TREMOR_AMP` | `0.3` | Simulated tremor amplitude, m/s² |
| `SIM_NOISE` | `0.02` | Gaussian noise, m/s² |
| `SIM_HAND_MM` | `200` | Simulated hand height above the ToF sensor, mm |
| `SIM_REACH_WOBBLE` | `0` | End-of-reach wobble amplitude, mm |
| `BOARD_HOST` / `BOARD_PORT` | `127.0.0.1` / `7700` | Relay address (through `adb forward`) |
| `DB_PATH` | `backend/data/tremorlab.db` | SQLite file (gitignored; health data never leaves the Mac) |
| `CORS_ORIGIN` | `http://localhost:5173` | The frontend origin allowed to call the API |
| `REPLAY_TEST_ID` | none | A specific test to replay |

Example: `SIM_TREMOR_HZ=7 make dev`. On the simulator you can also change these live with `PUT /api/sim` or the dev panel at `/dev`.

## Checking that it's up

```bash
curl -s localhost:8000/api/health
# {"status":"ok","sensor_source":"sim","connected":true,...}
```

The interactive API docs are at `http://localhost:8000/docs`. The contract they implement is in `docs/contracts.md`.
