# Tremor Lab: technical overview

**One-line pitch:** A 2-minute movement check you do at home. An Arduino UNO Q and the laptop
camera measure tremor, and each result is logged next to medication times, so patients,
caregivers and neurologists can see when tremor comes back after a dose. The sensor signal
analysis runs on the UNO Q itself; storage and the UI stay on the user's own laptop, with no cloud.

## 1. Architecture

```
MacBook                                              Arduino UNO Q
┌──────────────────────────────────┐               ┌───────────────────────────────┐
│ Browser (React, localhost:5173)  │               │ Linux side (Debian, Docker)   │
│  live canvas charts, MediaPipe   │  adb forward  │  Python relay: TCP :7700      │
│        │ REST + WebSocket        │ ─── 7700 ───▶ │  analysis server: TCP :7701   │
│ FastAPI backend (localhost:8000) │ ─── 7701 ───▶ │   (NumPy/SciPy signal math)   │
│  sensor sources → recorder → DB  │    USB-C      │        │ Bridge (MessagePack)  │
│  baselines, insights, SQLite     │               │ MCU sketch (STM32U585)        │
│                                  │               │  IMU @ 100 Hz, ToF @ 50 Hz    │
└──────────────────────────────────┘               └───────────────────────────────┘
```

**Core design choice:** the board senses *and* processes. The MCU samples on a hardware timer,
and the board's Qualcomm Linux side runs the signal analysis: tremor spectrum, posture gating,
reach smoothness, and the live spectrum every 250 ms. The Mac records, stores, computes
baselines and dose-timing insights, runs the MediaPipe tap test and serves the UI.

- **How:** the Mac sends each finished recording (and the live 8 s window) to an analysis
  server on the board (TCP 7701) and gets the result back. A 30 s rest analysis takes about
  90 ms round trip; a live-spectrum update about 35 ms. Results match the Mac's own
  computation to floating-point precision, because both run the same `analysis/` code with the
  same NumPy and SciPy versions.
- **Why this split:** the analysis code is pure functions, so the same file runs on both sides
  and is unit-tested on the Mac. Recording, reordering and clock mapping stay in one place.
  If the board ever stops answering, the Mac runs the same code locally, so a check never fails
  because of the link.
- **Offline board:** the board has no internet and its image has no SciPy, so
  `make board-deploy` unpacks NumPy and SciPy wheels into the app (`python/vendor/`).
- **USB-C only, no Wi-Fi:** the hackathon setup skipped Wi-Fi, so the link is
  `adb forward tcp:7700`. That makes it a plain TCP socket over the USB cable. It's also more
  reliable on a demo floor and keeps data off any network.

## 2. Hardware and firmware (`board/`)

**Sensors** (Modulino modules on the Qwiic bus):

- **Movement**, a 6-axis IMU (LSM6DSOX). It measures hand acceleration for the rest and
  posture tests.
- **Distance**, a time-of-flight sensor (VL53L4CD). It measures hand height for posture gating
  and the reach test.
- **LED matrix + RGB LED**, which give cues facing the user: countdown, hold, checkmark, blue
  while recording, green while streaming.

**Sketch (C++ on the MCU):**

- Samples are scheduled with `micros()`, never `delay()`.
- Each sample is timestamped by the MCU clock at the moment it's read.

**Relay (Python on the board's Linux side):** turns Bridge messages into newline-delimited JSON
over TCP 7700, and sends LED commands back the other way.

**Analysis server (same app, TCP 7701):** runs `tremorlab.analysis` on request and logs each run
(`analyzed tremor n=3000 in 93 ms: ok`), visible in `arduino-app-cli app logs`.

**Hardware findings** (all measured, recorded in [`hardware-notes.md`](hardware-notes.md)):

- **Batching backfired.** Sending 70 ints every 100 ms blocked the sketch for about 26 ms and
  dropped the IMU to 88 Hz. Sending one sample per message gave exactly 100.0 Hz IMU and
  50.0 Hz ToF.
- **Messages arrive bursty and out of order** (up to about 0.5 s late, ~0.5% reordered). The
  backend therefore orders samples by MCU timestamp, never by arrival time.
- **The ToF library repeats stale readings,** so sample rates are measured from timestamps,
  never assumed.

## 3. Backend (Python 3.12, FastAPI, NumPy, SciPy, SQLite)

**Sensor source abstraction.** All data enters through one `SensorSource` interface, which has
three implementations:

- `SimulatedSource`: synthetic tremor you can adjust live (frequency, amplitude, noise).
- `BoardSource`: the real hardware. It converts g to m/s², unwraps the `micros()` rollover,
  maps the MCU clock to Mac time, and auto-reconnects.
- `ReplaySource`: replays stored raw recordings through the same pipeline.

*Why:* the hardware never blocked software work, since everything was built against the
simulator first. The replay source is also the fallback if the board fails during judging.
Nothing downstream knows which source is active.

**Streaming.** One broadcaster task feeds three consumers:

- 30-second ring buffers;
- WebSocket fan-out to the browser;
- the active test recorder.

During a test it also pushes a live frequency spectrum every 250 ms.

**Signal analysis** (`analysis/`, executed on the UNO Q in board mode): pure functions with no
I/O, database or clock. Units are SI throughout. Full details and every tuning constant are in [`analysis.md`](analysis.md).

| Test | Method |
|---|---|
| **Rest / Posture tremor** | High-pass filter (4th-order Butterworth at 2 Hz) removes gravity and drift → Welch power spectrum → peak in the 3–12 Hz tremor band, refined by parabolic interpolation → band RMS strength → 0–100 log score |
| **Posture** | The ToF sensor gates the IMU data, so only time with the hand held at the target height counts |
| **Reach** | Savitzky–Golay smoothing of the descent curve. The residual gives smoothness, and the wobble ratio flags intention tremor near the target |
| **Finger tap** | MediaPipe hand landmarks → thumb-to-index distance normalized by hand size → peak detection → rate, amplitude decrement, rhythm variability |
| **Insights** | Tremor strength binned by hours since dose, "tremor typically returns after X h", personal baseline (shown only after 3+ checks) |

**Tuned on real data, not guesses.** The first detection threshold falsely flagged 29 of 44
windows of a still hand. That still-hand signal was real *physiological tremor* at 8–12 Hz. The
threshold was retuned against real board recordings: a still hand and a 5 Hz metronome shake.
After retuning there were 0 false detections, and the metronome was still detected in 100% of
windows.

**Storage:** SQLite through plain `sqlite3`, with no ORM. There are 6 tables (doses, checks,
tests, results, raw_samples, settings). *Why:* it's local and zero-config, and storing raw
samples is what makes replay possible.

## 4. Frontend (React, TypeScript, Vite)

**Stack:** Vite + React + TypeScript in strict mode, Tailwind v4 + shadcn/ui, Recharts for
dashboard charts, and `<canvas>` for live streams.

**Performance choice:** 100 Hz sensor samples go into React refs and are drawn with
`requestAnimationFrame`. They are never put in React state, which would mean 100 re-renders a
second.

**MediaPipe Hand Landmarker** runs the tap test on the webcam, in the browser:

- The model and WASM are served locally, with no CDN.
- Only 4 landmark points are sent to the backend. Video never leaves the browser.

**Screens:**

- the guided check flow (medication check-in → rest → posture → reach → tap → results);
- a Trends dashboard with Simple and Detailed views (Simple is plain language, Detailed has
  clinical depth);
- a printable doctor report;
- settings.

**Accessibility for people with tremor:** large hit targets, no hover-only interactions, and no
information shown by color alone. Every chart can be reached by keyboard.

See [`frontend.md`](frontend.md) for the code map and run modes.

## 5. Safety, privacy and trust

- **Not a medical device.** All user-facing text lives in one file, `copy.ts`, and a unit test
  fails the build if it contains "diagnosis", "you have", or advice to change medication.
- **Users are compared only to their own baseline,** never to population norms. Every insight
  shows its sample count.
- **No network calls with user data.** No cloud and no CDN at runtime.
- **Lifestyle tracking was cut on purpose.** Caffeine, sleep and stress were in the original
  plan but were removed after testing on seeded data: with about 50 checks, a modeled +10% sleep
  effect came out 8% *lower*. The app shows only what the data can support.

## 6. Engineering quality

- **Tests:** about 390 pytest tests, 49 vitest tests and 18 Playwright end-to-end tests.
- **Analysis was built test-first** on synthetic signals, then checked against real hardware
  recordings.
- **Contract tests:** [`contracts.md`](contracts.md) is the single source of truth for the REST,
  WebSocket and board interfaces, and a test fails if the API doesn't match it.
- **`make doctor`** checks every link in the hardware chain in order (adb → device → port
  forward → relay → sensors → sample rate) and gives a fix hint for each failure.
- **Gates:** ruff + mypy on the backend, `tsc --noEmit` + lint on the frontend. `make demo`
  starts a rehearsal mode (replay source + seeded database) as the backup if the hardware fails.

## Talking points

1. **"Hardware never blocks software":** the simulator, board and replay sources share one
   interface.
2. **Real signal processing, tuned on real data:** we found that a still hand has physiological
   tremor and retuned the threshold for it.
3. **Measured, not assumed:** every hardware fact was probed, including the batching discovery
   that brought the IMU from 88 Hz to 100 Hz.
4. **Processing on the UNO Q:** the board's Qualcomm side runs every sensor analysis, in about
   90 ms per test.
5. **Privacy by design:** everything runs locally, and video stays in the browser.
6. **Responsible framing:** the "not a medical device" rule is enforced by a test.
