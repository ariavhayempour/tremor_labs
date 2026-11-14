# PRD: Tremor Lab

> Instructions for the AI coding agent are in Section 13. Read the whole document before writing code, then implement one milestone at a time.

## 1. Overview

**Tremor Lab** is an at-home movement check for people already diagnosed with a tremor condition (e.g., Parkinson's disease, essential tremor). A guided 2-minute check runs four tests, each using a different sensor. Results are logged alongside medication times and lifestyle factors so patients, caregivers, and neurologists can see when and why tremor changes.

- **Context:** 24-hour hackathon, Qualcomm / Arduino UNO Q track.
- **Developer:** full-stack web developer, new to hardware, using VS Code with an AI coding agent.
- **Positioning:** a tracking tool, **not** a diagnostic or medical device. The app must never label a condition or give medical advice.

## 2. Problem

- In Parkinson's disease, levodopa's effect commonly "wears off" before the next dose. Doctors adjust dose timing based on paper diaries, which suffer from poor compliance, recall bias, and diary fatigue.
- Tremor fluctuates with medication, sleep, stress, and caffeine. A short clinic visit can't capture this.
- Research shows consumer-grade accelerometers can measure tremor frequency accurately.

**Goal:** replace a subjective paper diary with a 2-minute objective check that shows when tremor changes and what it correlates with.

## 3. Hardware (fixed; do not add components)

| Component | Role | Connection |
|---|---|---|
| Arduino UNO Q (ABX00173, 4 GB / 32 GB) | MCU (STM32U585) samples sensors; Linux side (Qualcomm QRB2210, Debian) runs Python backend | USB-C to MacBook for setup; Wi-Fi |
| Modulino Movement (6-axis IMU) | Rest + posture tremor | Qwiic, daisy-chained |
| Modulino Distance (Time-of-Flight) | Hand height gating; reach test | Qwiic, daisy-chained |
| MacBook Air (built-in camera) | Finger-tap test via MediaPipe; runs the browser UI | Wi-Fi to board |

**Hardware facts the code must respect:**
- The Qwiic connector is wired to the **MCU**, not Linux. Sensors are read in an Arduino sketch and passed to Linux through the Arduino App Lab bridge (RPC between MCU and Linux).
- Built-in **LED matrix** and **RGB status LEDs** are on the board and controlled from the sketch.
- Modulinos are daisy-chained: board → Modulino Distance → Modulino Movement (Movement at the end of the chain so it reaches the user's hand).

## 4. Users and Usage

**Primary user:** patient at a table, 2–6 checks per day, often timed around medication.
**Secondary:** caregiver (views dashboard), neurologist (reads printable report).

**Physical setup:** board at table edge with LED matrix facing user; Distance sensor flat on the table facing up; user holds Movement sensor; laptop behind.

## 5. The Check (user flow)

A check takes ~2 minutes. Steps in order:

1. **Check-in (10 s):** "Taken medication? When?" (one tap: now / X hours ago / not yet). Optional chips: caffeine (yes/no), sleep quality (1–5), stress (1–5), alcohol (yes/no).
2. **Rest test (30 s), Movement sensor:** forearm resting on thigh/armrest, palm up, sensor lying flat in the open palm, **not gripped** (gripping suppresses rest tremor). LED matrix shows countdown.
3. **Posture test (30 s), Movement + Distance:** arm extended, palm up holding sensor flat, hand held over the Distance sensor. Recording starts only when the hand is in the target height band; pauses with a prompt if the hand leaves the band.
4. **Reach test (3 attempts), Distance sensor:** user sets the Movement sensor down, starts with a fingertip ~25–30 cm above the Distance sensor, and slowly lowers it toward the sensor, stopping just above it.
5. **Tap test (10 s per hand), laptop camera:** user taps thumb and index finger together as fast and wide as possible.
6. **Results (15 s):** four scores, each compared to the user's own baseline, plus time since last dose.

## 6. Functional Requirements

### 6.1 Firmware (Arduino sketch on the MCU)
- Read Modulino Movement accelerometer + gyroscope at **100 Hz** with a fixed-interval timer (not `delay()` drift). Configure the IMU output data rate to ≥104 Hz if the library allows.
- Read Modulino Distance at its fastest stable rate (target 30–50 Hz).
- Timestamp every sample with the MCU clock (`micros()` or equivalent).
- Batch samples and send to Linux every ~100 ms via the bridge.
- Expose bridge-callable functions for the LED matrix and status LEDs: show countdown number, show "hold" icon, show checkmark, show idle animation, clear.
- Send an error/status message if a sensor isn't detected.

### 6.2 Sensor Source Abstraction (backend)
The backend must run **without hardware** for development. Implement a common interface with two implementations:
- `BoardSource`: receives batches from the MCU bridge on the UNO Q.
- `SimulatedSource`: generates realistic data on any machine:
  - IMU: gravity (~9.81 m/s² on one axis) + configurable tremor sinusoid (frequency Hz, amplitude) + Gaussian noise + slow drift.
  - ToF: configurable hand height with noise; scripted descent for the reach test with optional wobble near the end.
  - Controllable from a dev panel in the UI and via env vars/CLI (e.g., `SIM_TREMOR_HZ=5`, `SIM_TREMOR_AMP=0.3`).
- Select with `SENSOR_SOURCE=sim|board`.

### 6.3 Signal Processing (Python: NumPy + SciPy)
Analysis code must be pure functions with no I/O, fully unit-tested.

**Common:** compute the actual sample rate from timestamps; never assume exactly 100 Hz. Discard the first and last 2 s of each recording.

**Rest and posture tremor:**
1. High-pass each accelerometer axis (4th-order Butterworth, 2 Hz cutoff, zero-phase `filtfilt`) to remove gravity and slow drift.
2. Compute the PSD per axis with Welch's method (window ≈ 4 s, 50% overlap); sum across axes.
3. **Peak frequency:** max PSD in 3–12 Hz.
4. **Tremor strength:** RMS of the signal band-passed to 3–12 Hz (report in m/s² and as a 0–100 display score with documented mapping).
5. **Tremor detected?** Only if peak power exceeds a noise-floor threshold (constant, tuned with simulator and real still-hand data). Otherwise report "no clear tremor."
6. Also return the spectrum (frequencies + PSD) for display.

**Posture gating:** target band = height recorded at test start ± 30 mm (or a configurable absolute band). Only samples where ToF is within band count toward analysis; require ≥ 20 s of valid data.

**Reach test (per attempt, then averaged):**
1. Detect the descent: start when distance drops below the starting height minus 20 mm, end when distance < 40 mm or stops decreasing for 0.5 s.
2. Smooth with Savitzky–Golay; residual = raw − smoothed.
3. **Smoothness score:** RMS of residual across the whole descent.
4. **End-of-reach wobble ratio:** residual RMS in the final 50 mm ÷ residual RMS before that.
5. Return the descent curve + residual for display.

**Tap test:** the browser sends landmark time series; the backend analyzes:
1. Signal = distance between thumb tip (landmark 4) and index tip (landmark 8), normalized by wrist (0) to middle-finger MCP (9) distance.
2. Detect taps as peaks with minimum prominence (configurable).
3. Metrics: taps per second, mean tap amplitude, **amplitude decrement** = (mean amplitude in last 3 s − first 3 s) ÷ first 3 s, rhythm variability = coefficient of variation of inter-tap intervals.

**Baselines:** after ≥ 3 checks, show each metric as % vs. the user's average for that test. Before that, show "building your baseline."

### 6.4 Backend API (Python, FastAPI, SQLite)
- Runs on the UNO Q Linux side in production; runs on the Mac in simulator mode for development. Same code.
- CORS enabled for the frontend origin.
- All health data stored locally in SQLite. No cloud calls.

**REST endpoints:**
- `POST /api/checks` → create a check with check-in answers; returns `check_id`
- `POST /api/checks/{check_id}/tests` body `{ "type": "rest" | "posture" | "reach" | "tap", "hand": "left" | "right" }` → starts recording (except tap); returns `test_id`
- `POST /api/tests/{test_id}/stop` → stops recording, runs analysis, returns result
- `POST /api/tests/{test_id}/tap-data` → body: landmark time series; runs tap analysis, returns result
- `GET /api/checks?from=&to=` → list checks with results
- `GET /api/insights/dose-response` → tremor strength binned by hours since last dose (0.5 h bins, with counts)
- `GET /api/insights/factors` → metric averages split by caffeine / sleep / stress / alcohol, with sample counts
- `GET /api/insights/profile` → current vs. first-week values per test
- `GET/PUT /api/settings` → dose times, reminder schedule, tested hand, posture height band
- `GET /api/report?days=14` → data for the printable doctor report
- `POST /api/led` → `{ "command": "countdown" | "hold" | "check" | "idle" | "clear", "value": int? }`
- `GET /api/health` → backend status, sensor source, sensors detected

**WebSocket `/ws`** (server → client):
```json
{ "type": "imu", "t0": 1731600000.123, "fs": 100.0, "samples": [[0.01, 9.80, 0.12, 0.3, -0.1, 0.0]] }
{ "type": "tof", "t0": 1731600000.123, "samples_mm": [212, 211, 213] }
{ "type": "spectrum", "freqs": [0, 0.25], "psd": [0.001, 0.002], "peak_hz": 5.0 }
{ "type": "position", "tof_mm": 214, "in_band": true }
{ "type": "status", "recording": true, "seconds_left": 18 }
```
Send raw IMU/ToF at ~10 Hz batches; send `spectrum` at ~4 Hz during tremor tests.

### 6.5 Data Model (SQLite)
- `checks(id, created_at, minutes_since_dose, caffeine, sleep_quality, stress, alcohol, notes)`
- `tests(id, check_id, type, hand, started_at, ended_at, status)`
- `results(test_id, peak_hz, strength_ms2, strength_score, tremor_detected, smoothness, wobble_ratio, taps_per_sec, tap_amplitude, amplitude_decrement, rhythm_cv, valid_seconds)`
- `raw_samples(test_id, sensor, payload_json)` (raw batches for replay and re-analysis)
- `doses(id, taken_at, label)`
- `settings(key, value)`

### 6.6 Frontend (React + TypeScript + Vite)
- **Camera constraint:** browsers only allow camera access on secure origins. **Always serve the frontend from the Mac at `http://localhost`** (Vite dev server, or a local static server for the demo), connecting to the board's API by IP via `VITE_API_BASE`. Do not serve the UI from `http://<board-ip>`.
- MediaPipe Hand Landmarker (`@mediapipe/tasks-vision`) runs in the browser for the tap test.
- Live waveforms and spectra: draw on `<canvas>` (or uPlot) and keep streaming data in refs, not React state, to avoid re-render overhead.
- Dashboard charts: Recharts.

**Screens:**
1. **Home:** next scheduled check, "Start check" button, streak, backend/sensor status indicator.
2. **Check-in:** large one-tap buttons and chips.
3. **Test runner:** step pills (Rest → Posture → Reach → Tap), instruction text, countdown, live metrics, live visualization per test:
   - Rest/posture: scrolling waveform + live spectrum with peak highlighted; posture shows a height guide ("raise your hand a little").
   - Reach: descent curve drawn live; final 50 mm highlighted when wobble is high.
   - Tap: camera feed with thumb/index landmarks overlaid and a live tap counter.
4. **Results:** four score cards vs. baseline, time since last dose.
5. **Dashboard (14 days):** metric cards (checks completed, typical "tremor returns after X h", factor effects), dose-response chart with dose markers, daily timeline, movement profile (four tests vs. first week), recent checks list.
6. **Doctor report:** printable one-page view (CSS `@media print`), every insight shows its sample count.
7. **Settings:** dose times, reminders, tested hand, posture band.
8. **Dev panel** (dev builds only): simulator controls (tremor Hz, amplitude, noise, hand height, trigger reach descent).

**Copy rules:** plain, friendly language. Never say "diagnosis," "you have," or recommend medication changes. Footer on dashboard and report: "Tremor Lab is a tracking tool, not a medical device. Discuss results with your doctor."

### 6.7 Demo Data Seeder
`scripts/seed.py` generates 14 days of realistic, deterministic data (fixed random seed):
- 3 doses/day at 08:00, 13:00, 18:00; 3–4 checks/day.
- Rest tremor strength low ~1 h after each dose, rising from ~3 h, high before the next dose.
- Caffeine days ~20% higher tremor; poor sleep ~10% higher.
- Tap speed slightly higher when medication is working; mild amplitude decrement throughout.
- Peak frequency 4.5–5.5 Hz.

## 7. Repository Structure
```
tremor-lab/
├── PRD.md
├── board/                    # Arduino App Lab app for the UNO Q (sketch + Python bridge)
├── backend/
│   ├── tremorlab/
│   │   ├── analysis/         # pure signal-processing functions
│   │   ├── sources/          # SensorSource interface, SimulatedSource, BoardSource
│   │   ├── api/              # FastAPI routes + websocket
│   │   ├── db/               # SQLite schema + queries
│   │   └── main.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/                 # Vite + React + TypeScript
└── scripts/
    └── seed.py
```
The `board/` folder must follow the real App Lab project structure (see Section 13). If App Lab requires a different layout or limits which Python packages can run, the backend package should be importable from the App Lab Python entry point, or run as a separate process on the board.

## 8. Non-Functional Requirements
- **Latency:** sensor sample to on-screen waveform < 200 ms.
- **Accuracy check:** simulated 5.0 Hz tremor must be reported as 5.0 ± 0.25 Hz; a real hand shaken to a 300 BPM metronome should read ~5 Hz.
- **Privacy:** no external network calls with user data.
- **Resilience:** if sensors disconnect, the UI shows a clear message and the test can be retried; no crash.
- **Code quality:** typed Python (type hints) and TypeScript; analysis functions documented with units.

## 9. Milestones and Acceptance Criteria

**M0: Scaffold (no hardware)**
- Repo structure created; backend runs with `SENSOR_SOURCE=sim`; frontend runs on localhost and shows live simulated waveform via WebSocket.
- ✅ Done when: changing `SIM_TREMOR_HZ` changes the waveform on screen.

**M1: Tremor analysis**
- Rest + posture analysis implemented with unit tests (synthetic 4, 5, 6, 8 Hz signals; still-hand noise → "no clear tremor").
- Live spectrum shown during the test.
- ✅ Done when: all analysis tests pass and simulated 5 Hz shows a 5.0 Hz peak in the UI.

**M2: Hardware bring-up (human does physical steps)**
- Sketch reads both Modulinos, batches data, sends via bridge; `BoardSource` receives it; LED matrix commands work.
- ✅ Done when: shaking the real sensor produces a live waveform in the browser and measured sample rate is ~100 Hz.

**M3: Full check flow**
- Check-in → rest → posture (with ToF gating) → reach → tap → results; all stored in SQLite.
- ✅ Done when: a full check completes end-to-end on real hardware and results appear in the database.

**M4: Dashboard and insights**
- Seeder, dashboard, dose-response, factors, movement profile, recent checks.
- ✅ Done when: seeded data clearly shows the wearing-off pattern and caffeine effect.

**M5: Polish**
- Doctor report, settings, LED matrix cues throughout the flow, error states, demo script rehearsal mode.

**Cut order if short on time:** factors comparison → doctor report → settings screen → LED idle animation. M0–M4 is a complete demo.

## 10. Demo Script (3 min)
1. Problem: paper diaries, recall bias (30 s).
2. Judge completes a live check (75 s).
3. Metronome trick: shake at 300 BPM, peak lands at 5 Hz (20 s).
4. Dashboard with 14 days of seeded data: wearing-off curve, caffeine effect, movement profile (40 s).
5. Close: on-device processing and privacy, why the UNO Q's MCU timing matters (15 s).

## 11. Risks and Mitigations
| Risk | Mitigation |
|---|---|
| Bridge can't sustain 100 Hz | Larger batches; if still limited, lower to 50 Hz (still valid for tremor up to ~12 Hz with margin) and document |
| App Lab Python environment can't run FastAPI/SciPy | Run backend as a separate process on the board, or fall back to running backend on the Mac with the board streaming raw batches |
| Hackathon Wi-Fi blocks device-to-device traffic | Use a phone hotspot for board + Mac |
| Camera blocked in browser | Serve frontend from localhost only |
| MediaPipe struggles in poor lighting | Desk lamp; on-screen "move into the light" prompt when no hand is detected |
| Hardware failure during judging | Simulator mode + pre-recorded raw samples replayable through the same pipeline |

## 12. Out of Scope
Diagnosis or condition classification, multi-user accounts and authentication, cloud sync, mobile app, clinical validation, gyroscope-based analysis (accelerometer only for v1).

## 13. Instructions for the AI Coding Agent
1. **Work one milestone at a time**, in order. At the end of each, summarize what was built, how to run it, and how to verify the acceptance criteria.
2. **Do not guess hardware or App Lab APIs.** Before writing firmware or bridge code, inspect the installed Arduino_Modulino library examples and an Arduino App Lab example app to confirm: project structure, the bridge/RPC API between sketch and Python, LED matrix API, and IMU/ToF configuration functions. If something can't be confirmed, stop and ask the human to check (e.g., open an example in App Lab and paste its files).
3. **Build everything against `SimulatedSource` first.** Hardware-dependent code must be isolated in `board/` and `BoardSource`.
4. **Mark physical steps clearly** (plugging in, flashing via App Lab, Wi-Fi setup) as "HUMAN ACTION REQUIRED" with exact steps.
5. **Keep analysis pure and tested.** Every analysis function gets pytest tests with synthetic signals before it's used in the UI.
6. **Prefer simple, well-known libraries:** FastAPI, uvicorn, NumPy, SciPy, React, Vite, Recharts, `@mediapipe/tasks-vision`. Ask before adding others.
7. **Never write diagnostic language** in UI copy, comments shown to users, or reports.
8. When unsure about a requirement, choose the simplest option that meets the acceptance criteria and note the assumption.
