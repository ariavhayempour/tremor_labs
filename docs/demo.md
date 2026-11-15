# Demo script (3 minutes)

The judging walkthrough, with exact steps and a fallback for every step that touches hardware. The screens and routes are the ones in `docs/frontend-plan.md`. If a button label changes in the UI, update it here.

## Before the judges arrive (10 min)

1. **HUMAN ACTION REQUIRED: board.** Plug the UNO Q into the Mac over USB-C, with both Modulinos on the Qwiic chain. From the repo root, run `make board-deploy` (not App Lab: its copy lacks the analysis code and vendored SciPy). It ends with `✓ App "tremorlab" started successfully`, and the matrix shows the idle animation.
2. From the repo root, run `make seed`. This **replaces** `backend/data/tremorlab.db` with 14 days of demo data that ends yesterday, plus one replayable check from about 10 minutes ago.
3. Run `make dev SENSOR_SOURCE=board`. It runs `make board-link` first.
4. In a second terminal, run `make doctor`. Every line should be `PASS` (adb → device → forward → relay → sensors → rates → analysis). The `analysis` line proves the board is doing the signal processing. If any line fails, follow its hint. If it still fails, use the [fallback](#fallback-no-hardware).
5. Open `http://localhost:5173` in Chrome (it must be `localhost`, because the camera needs a secure origin). Allow the camera when asked.
6. Have the metronome ready at **300 BPM** (5 Hz), on a phone app or a browser tab.
7. Set up a desk lamp for the tap test, since MediaPipe needs a well-lit hand.

## The script

| Time | Segment | What to do | What the judge sees |
|---|---|---|---|
| 0:00–0:30 | **Problem** | Talk over the Home screen. People with a tremor condition and their neurologist rely on paper diaries and memory to answer "when does it get worse?". Recall is poor, and clinic visits are minutes long. | Home, with the matrix idle. |
| 0:30–1:45 | **Live check** | 1. Click **Start check**. 2. Check-in: click **1 h** (the judge "took a dose an hour ago"). 3. **Rest:** the judge rests a forearm on the table, palm up, with the Movement sensor lying flat in the open palm, **not gripped**. Click **Start**. 4. **Posture:** arm held out, palm up over the Distance sensor. Recording runs only while the hand is in the band. 5. **Reach:** sensor set down, fingertip about 25–30 cm above the Distance sensor, lowered slowly three times. 6. **Tap:** thumb–index taps in front of the camera for 10 s, with the hand chosen at the start of the check. 7. **Results:** four cards, each against the person's own baseline, plus the time since the dose. | The live waveform and spectrum while recording; the matrix counts down, shows `hold` when out of band and a check mark when done. |
| 1:45–2:05 | **Metronome trick** | Start a new Rest test. Hold the sensor flat and shake it in time with the 300 BPM metronome. | The spectrum peak lands at about **5 Hz** (5.07 Hz measured on this hardware). |
| 2:05–2:45 | **Dashboard** | Click **Dashboard**. Point out: (a) the **wearing-off curve**: rest tremor strength by hours since dose, lowest about 1 h after a dose and back to usual after about **3 h**; (b) the **movement profile**: first week vs the current week for each test; (c) the daily timeline and the streak. Then click **Report** and show the printable one-page summary for the neurologist, with `n=` on every number. | Charts built from 14 days of seeded data plus today's live check. |
| 2:45–3:00 | **Close** | The UNO Q does the signal processing: every tremor spectrum and score you saw was computed on its Qualcomm Linux side (`arduino-app-cli app logs` shows each run). The laptop stores the history and draws the UI: no cloud and no account, and health data never leaves these two devices. The UNO Q's MCU samples the IMU on a hardware timer at 100 Hz, independent of Linux scheduling. That even timing is what makes a 5 Hz peak trustworthy. It's a tracking tool, not a medical device. | — |

Wording rule for the talk track: describe what is measured ("tremor strength was lower an hour after the dose"). Never say "diagnosis", "you have…" or anything that suggests changing medication.

## LED cues on the matrix

| Moment | LED command |
|---|---|
| Test intro | `hold` |
| Recording | `recording 1`, plus `countdown n` each second |
| Out of band | `hold` |
| Result | `check`, then `recording 0` |
| Home | `idle` |

## Fallback: no hardware

Use this if `make doctor` fails, the board disconnects mid-demo, or the camera is blocked.

1. Press Ctrl-C in the `make dev` terminal.
2. Run `make demo`. It copies the seeded DB to `backend/data/demo.db` and runs the backend with `SENSOR_SOURCE=replay`.
3. Refresh the browser.

What changes in each segment:

| Segment | With `make demo` |
|---|---|
| Live check | Rest and posture replay the stored check's samples through the same pipeline, so the waveform and spectrum still move and the results are real analysis output. Say that it's a replay of a recorded check. The reach and tap steps still need their sensors: skip them, or use the camera for tap if it works. |
| Metronome trick | The replayed rest recording peaks at 5.0 Hz. Show that instead, and say it was recorded earlier. |
| Dashboard and report | Same seeded data, so nothing changes. |

Other failures:

| Failure | Fix |
|---|---|
| Board unplugged mid-test | The UI shows the disconnect message. Re-plug, run `make board-link`, then click **Retry**. |
| `make doctor` fails at `relay` or `sensors` after a re-plug | Power-cycle the board: unplug it for 5 s, start the app again in App Lab, then run `make board-link`. |
| Tap finds no hand | Turn on the lamp and move the hand closer. Or skip tap: the other three cards still show. |
| `make seed` was never run | `make demo` runs it automatically when the DB is missing. |

## Verified

`make demo` was run end to end on 2026-11-14 with the board unplugged:
- the seed wrote 42 doses and 55 checks, plus 1 replay check;
- `/api/health` reported `sensor_source: replay` at 100 Hz IMU and 40 Hz ToF;
- the dashboard insights returned the wearing-off curve (returns after 3.0 h, a 15-day streak);
- a 30 s rest test on the replay source finished `done` with a 5.00 Hz peak.

The UI walkthrough and the board's LED cues still need the human rehearsal once the frontend is merged.
