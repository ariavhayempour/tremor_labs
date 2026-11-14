# Tremor Lab (Mac-hosted FastAPI + React, Arduino UNO Q sensors)

## Tech Stack

- Backend language: Python 3.12 (managed by `uv`; system Python 3.9 is never used), fully type-hinted
- Backend: FastAPI + uvicorn, Pydantic v2, NumPy + SciPy, SQLite via stdlib `sqlite3` (no ORM)
- Frontend language: TypeScript (strict mode)
- Frontend: Vite + React, react-router, Tailwind CSS v4 + shadcn/ui, Recharts,
  `@mediapipe/tasks-vision` (model + WASM served from `frontend/public/`)
- Frontend package manager: pnpm
- Board: Arduino UNO Q via Arduino App Lab. The sketch (MCU) uses `Arduino_RouterBridge`,
  `Arduino_Modulino` and `Arduino_LED_Matrix`; the Python relay uses `arduino.app_utils`
- Board ↔ Mac link: USB-C only. `adb forward tcp:7700 tcp:7700` to the relay's TCP server (no Wi-Fi)
- Tests: pytest (analysis, sources, API, seeder), vitest (copy rule), Playwright (smoke)
- Quality: ruff + mypy (backend), `tsc --noEmit` + lint (frontend)
- Key dirs: `backend/tremorlab/{analysis,sources,stream,api,db}/`, `frontend/src/{api,viz,screens}/`,
  `board/tremorlab/{sketch,python}/`, `scripts/`

## Purpose

- At-home 2-minute movement check (rest, posture, reach, tap) for people already
  diagnosed with a tremor condition. Results are logged next to medication times and
  lifestyle factors so patients, caregivers and neurologists can see when tremor changes
- A **tracking tool, not a medical device**. It never labels a condition or gives medical advice
- 24-hour hackathon build (Qualcomm / Arduino UNO Q track); everything runs locally on the MacBook
- Requirements: `PRD.md`. Design spec: `docs/superpowers/specs/2026-11-14-tremor-lab-design.md`
  (where they disagree, the spec wins; the spec is local to the backend developer and untracked)
- Frontend work follows `docs/frontend-plan.md` and the API contract `docs/contracts.md`. Both are tracked,
  so a frontend-only contributor needs nothing from `docs/superpowers/`

## Architecture Rules

- The backend, analysis and SQLite run on the **Mac**. The board runs only the sketch
  and a thin relay in `board/tremorlab/python/main.py` (stdlib + `arduino.app_utils`,
  forwarding only, no logic)
- `backend/tremorlab/analysis/` holds pure functions only: no I/O, no DB, no clock,
  typed, units in every docstring. Every analysis function gets pytest tests with
  synthetic signals **before** it is used by the API or UI
- All sensor data enters through the `SensorSource` interface (`sources/`):
  `SimulatedSource`, `BoardSource`, `ReplaySource`, selected by `SENSOR_SOURCE=sim|board|replay`.
  Sources emit SI units (m/s², deg/s, mm, epoch seconds); nothing downstream knows
  which source is active
- Hardware-dependent code lives only in `board/` and `sources/board.py`. Build every
  feature against `SimulatedSource` first; hardware must never block software work
- `api/` routes call `stream/`, `analysis/` and `db/`. Only `db/` runs SQL. Schema lives
  in `db/schema.sql`
- Live streaming data stays in React refs and is drawn on `<canvas>` with
  `requestAnimationFrame`, never in React state per sample. Dashboard charts use Recharts
- The frontend is always served from `http://localhost` (camera access requires a secure
  origin) and reaches the API through `VITE_API_BASE`
- No external network calls with user data. No CDNs at runtime, no cloud services
- **Never guess hardware or App Lab APIs.** Check the verified-facts table in the
  design spec (§2). If something is marked UNVERIFIED, confirm it against the official
  examples (`arduino/app-bricks-examples`, the `Arduino_Modulino` library) or stop and
  ask me to open the example in App Lab and paste its files
- Mark every physical step (plugging in, flashing via App Lab, adb setup) as
  **HUMAN ACTION REQUIRED**, with exact steps and the visible success signal
- **Never write diagnostic language** in UI copy, user-facing messages or reports. All
  user-facing strings live in `frontend/src/copy.ts`. Never use "diagnosis", "you have",
  or advice to change medication

## Development Workflow

First time:
- **HUMAN ACTION REQUIRED:** install Arduino App Lab and run `brew install android-platform-tools`
- Then run `uv sync` (in `backend/`) and `pnpm install` (in `frontend/`)

These commands are created in M0 and the targets are defined in the root `Makefile`:

```bash
# Build/Run
make dev                          # backend (localhost:8000) + frontend (localhost:5173), SENSOR_SOURCE=sim
make dev SENSOR_SOURCE=board      # runs `make board-link` (adb forward) first
make board-link                   # adb forward tcp:7700 tcp:7700
make seed                         # 14 days of deterministic demo data (scripts/seed.py)
make demo                         # rehearsal mode: replay source + seeded DB

# Test (run before declaring done)
make test                         # pytest (backend) + vitest (frontend)
make test-e2e                     # Playwright smoke

# Quality
make lint                         # ruff + frontend lint
make typecheck                    # mypy + tsc --noEmit
make build                        # vite build (the gate: must exit 0, zero TS errors)

# Hardware diagnostics
make doctor                       # checks adb → device → forward → relay → sensors → Hz, with fix hints
make rate                         # prints measured IMU / ToF sample rates
```

## Code Style

- Python: type hints on every function, `ruff` formatting, snake_case modules, dataclasses
  or Pydantic models at boundaries, named constants for every tuning threshold
- TypeScript: strict mode, no `any` in committed code, explicit types on public boundaries;
  2-space indent, single quotes, trailing commas
- Frontend filenames: PascalCase for components (`Waveform.tsx`), camelCase for hooks and
  modules (`useSensorStream.ts`, `client.ts`); one component per file
- Sketch: schedule with `micros()`, never `delay()`; do not `Bridge.call` from inside a
  Bridge callback
- Comments: default to one concise line for a non-obvious why; push anything longer
  into `docs/` (see rule 2). No multi-paragraph docstring essays (analysis docstrings
  state units and inputs/outputs, briefly), no restating what the code does, no comment rot
- Ask before adding any dependency beyond the approved list in the design spec (§1, D7–D8,
  plus the PRD list), changing a package manager, adding another UI component library,
  or introducing environment variables or secrets beyond those in `config.py`

## Documentation

- `docs/` - all project documentation (architecture, decisions, hardware notes, structure)
- `docs/superpowers/` - design specs and plans (planning artifacts, untracked)
- `docs/frontend-plan.md` - frontend implementation plan (tracked; owned by the frontend contributor)
- `docs/contracts.md` - REST / WebSocket / board wire contracts (tracked; changed only on `main`)
- `PRD.md` - original product requirements

## Working Rules

Read and follow all of them.

### 1. Read this file first

Always read this `CLAUDE.md` at the start of every session, and again whenever
context is cleared. Understand the guidelines below and follow them throughout
the session.

### 2. Documentation lives in `docs/`

All project documentation belongs in Markdown files under `docs/`. Keep
code comments to a single concise line — enough to clarify intent, never more.
Push anything longer into the docs.

### 3. Review the docs before acting

Before planning or building anything, review the relevant files in
`docs/` (and the design spec in `docs/superpowers/specs/`) to understand
existing dependencies, decisions, and structure. Let the docs inform the plan.

### 4. Never commit, stage, or push

Do not run `git add`, `git commit`, or `git push` — ever, unless I give explicit
one-time permission for a specific action. When a task is complete, tell me so
and stop; I will commit manually.

### 5. Planning artifacts stay untracked

All planning artifacts — `docs/superpowers/`, the `tasks/` folder, `SPEC.md`,
`plan.md`, `todo.md` — always remain untracked. Never stage or commit them.

### 6. No co-author tags in commits

When you are granted one-time permission to commit under rule 4, never include
co-author trailers (e.g. `Co-Authored-By:`) in the commit message.

### 7. Code comments describe the code, not the plan

Code-file comments must never reference planning-artifact identifiers — milestone
numbers (`M3`), task numbers (`T5`), decision IDs (`D6`), spec section numbers (`§8`),
or similar. Those are mutable and get reorganized; a comment pinned to one reads as
stale the moment it changes. Explain the technical reason instead: functionality,
behavior, constraints, or dependencies. (Cross-references between docs may cite
those identifiers freely — this rule is about code comments only.)

### 8. One milestone at a time

Work milestones in order (M0 → M0.5 → M1 → … → M5). At the end of each, summarize
what was built, how to run it, and how to verify its acceptance criteria. Then stop.

## Common Mistakes

- Run `make build`, `make typecheck`, `make lint`, and `make test` before declaring a task done
- Add code-file comments longer than one line into a respective `docs` file.
- Assuming exactly 100 Hz: always compute the sample rate from timestamps
- Forgetting the unit conversion: Modulino Movement reports **g** and **deg/s**, so
  `BoardSource` converts to m/s²
- Putting per-sample streaming data in React state instead of refs
- Writing firmware or relay code from memory instead of the verified examples
