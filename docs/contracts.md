# Tremor Lab contracts

The single source of truth for every interface between the frontend, the backend, and the board.

- **Change process:** changed only by the backend owner. Any other branch that needs a change asks for it. After it lands, every branch merges it and updates its mirrors (e.g. `frontend/src/api/types.ts`).
- **Mirrors in code:** REST bodies are `backend/tremorlab/api/schemas.py`. The source protocol is `backend/tremorlab/sources/base.py`. The DB schema is `backend/tremorlab/db/schema.sql`.
- **Tests:** `backend/tests/test_contracts.py` parses the endpoint headings below (`### \`METHOD /path\``) and fails if the app doesn't register one.

## Conventions

- **Base URL:** `VITE_API_BASE`, default `http://localhost:8000`. The WebSocket is `ws://localhost:8000/ws`.
- **JSON field names are snake_case** everywhere. TS mirrors use the same names.
- **Timestamps:**
  - REST: ISO-8601 strings with a UTC offset, e.g. `"2026-11-14T15:04:05.123000Z"` (a `+00:00` offset is also valid; parse with `new Date()`).
  - WebSocket: epoch seconds (float).
- **Units:** acceleration m/s², gyroscope deg/s, distance mm, frequency Hz, durations s. The DB and the API report the same units.
- **Nullable fields** are always present in responses, with the value `null`. They are never omitted.
- **Errors:** every non-2xx response has the body `ErrorOut`:
  ```json
  { "error": "test_active", "message": "A test is already recording." }
  ```
  `message` is friendly text, but the frontend shows its own copy keyed by `error`.

- **No lifestyle factors.** Caffeine, sleep, stress and alcohol aren't collected or reported. Their effects on tremor are small, self-reported and confounded by dose timing, so they can't be shown reliably at this data volume. The check-in rejects those fields with 422, and there's no factors insight.

### Error codes (`ErrorOut.error`)

| Code | Status | When |
|---|---|---|
| `validation_error` | 422 | Body or query fails validation. `message` names the first bad field. |
| `not_found` | 404 | Unknown check, test or route. |
| `test_active` | 409 | Starting a test while another one has been recording for less than 120 s. |
| `invalid_state` | 409 | Stop/mark on a test that isn't recording, or `tap-data` on a non-tap or finished test. |
| `not_implemented` | 501 | Endpoint exists but isn't built yet (only during development). |

### `fail_reason` codes

Stored on failed tests and returned as `TestOutcomeOut.fail_reason` / `TestOut.fail_reason`.

| Code | Meaning |
|---|---|
| `insufficient_valid_data` | Recording too short after trimming, or under 20 s of in-band posture time. |
| `no_descent_detected` | Reach: no attempt window contains a descent. |
| `no_taps_detected` | Tap: fewer than 3 taps found. |
| `sensor_disconnected` | The recording has a data gap longer than 1 s. |
| `interrupted` | The recording was abandoned (backend restart, or a new test started after 120 s). |

The frontend also uses `skipped` for steps the user skips. The backend never stores or returns it.

### Shared types

| Name | Values |
|---|---|
| `TestType` | `"rest" \| "posture" \| "reach" \| "tap"` |
| `Hand` | `"left" \| "right"` |
| `TestStatus` | `"recording" \| "analyzing" \| "done" \| "failed"` |
| `FailReason` | the codes above |
| `LedCommand` | `"countdown" \| "hold" \| "check" \| "idle" \| "clear" \| "recording"` |

### Type names

The frontend mirror names (left) match the Pydantic models (right). Where they differ, the TS name drops the `Out` suffix.

| TS (`types.ts`) | Pydantic (`schemas.py`) |
|---|---|
| `Health` | `HealthOut` |
| `SimParams` | `SimParamsOut` (request: `SimUpdateRequest`) |
| `TestOutcome` | `TestOutcomeOut` |
| `LedRequest`, `TapDataIn`, `SettingsUpdate` | same |
| every other REST name | same |

---

## REST endpoints

### `GET /api/health`

Response `HealthOut`:
```json
{
  "status": "ok",
  "sensor_source": "sim",
  "connected": true,
  "sensors_detected": { "movement": true, "distance": true },
  "imu_hz": 100.0,
  "tof_hz": 40.0
}
```
- `sensor_source`: `"sim" | "board" | "replay"`.
- `imu_hz` / `tof_hz`: measured from timestamps over the last 5 s, or `null` when unknown.

### `GET /api/sim`

**Only registered when `sensor_source == "sim"`;** otherwise 404. Response `SimParamsOut`:
```json
{ "tremor_hz": 5.0, "tremor_amp": 0.3, "noise": 0.02, "hand_mm": 200.0, "reach_wobble": 0.0 }
```
Units: Hz, m/s², m/s², mm, mm.

### `PUT /api/sim`

Body `SimUpdateRequest`: any subset of the `SimParamsOut` fields, and/or `"action": "descent"` (starts a scripted 300 → 30 mm reach descent over about 2.5 s).
```json
{ "tremor_hz": 7 }
{ "action": "descent" }
```
Limits: `tremor_hz` 0–30 (exclusive of 0), `tremor_amp` 0–5, `noise` 0–1, `hand_mm` 0–2000, `reach_wobble` 0–50.
Response: the updated `SimParamsOut`. Changes take effect on the next 100 ms batch.

### `POST /api/checks`

Body `CheckInRequest`:
```json
{
  "medication": "hours_ago",
  "hours_ago": 2,
  "notes": null
}
```
- `medication` is required: `"now" | "hours_ago" | "not_yet"`.
- Everything else is optional and nullable.
  - `hours_ago`: 0–24, used only with `"hours_ago"`. The UI offers 0.5, 1, 2, 3 and 4 (shown as "4 h+").
  - `notes`: up to 2000 characters.
- **Dose logging:**
  - `now` or `hours_ago` logs a dose at `now − hours_ago`, unless one already exists within ±30 min of that time. `minutes_since_dose` is measured from that dose.
  - `not_yet` uses the latest logged dose at or before now. With no dose ever logged, `minutes_since_dose` is `null`.

Response **201** `CheckCreated`:
```json
{ "check_id": 12, "minutes_since_dose": 120.0 }
```

### `GET /api/checks`

Query:
- `from`, `to` (ISO-8601, both optional and inclusive).
- `details` (boolean, default `true`). With `details=false`, every `result.details` is `{}` and all the metric fields stay. Use it for lists and the dashboard: the curves are about 35 KB per check. The Results screen keeps using `GET /api/checks/{check_id}`, which always includes them.

Response: `CheckOut[]`, newest first.

`CheckOut`:
```json
{
  "id": 12,
  "created_at": "2026-11-14T15:04:05Z",
  "minutes_since_dose": 120.0,
  "notes": null,
  "dose_id": 7,
  "tests": [
    { "id": 40, "type": "rest", "hand": "right", "status": "done", "fail_reason": null, "result": { "...": "ResultOut" } }
  ]
}
```
`TestOut`: `id`, `type`, `hand`, `status: TestStatus`, `fail_reason: FailReason | null`, `result: ResultOut | null`. Tests are in the order they were started.

### `GET /api/checks/{check_id}`

Response `CheckSummaryOut`, which feeds the Results screen:
```json
{
  "check": { "...": "CheckOut" },
  "cards": [
    { "test": "rest", "metric": "strength_score", "value": 42.0, "unit": "score", "baseline_pct": 12.5, "baseline_n": 5, "status": "done" },
    { "test": "posture", "metric": "strength_score", "value": 30.1, "unit": "score", "baseline_pct": null, "baseline_n": 2, "status": "done" },
    { "test": "reach", "metric": "smoothness", "value": 3.4, "unit": "mm", "baseline_pct": -8.0, "baseline_n": 5, "status": "done" },
    { "test": "tap", "metric": "taps_per_sec", "value": 3.9, "unit": "taps/s", "baseline_pct": 4.1, "baseline_n": 5, "status": "done" }
  ]
}
```
- Always 4 cards, in the order rest, posture, reach, tap.
- `metric` and `unit` per test:
  - rest and posture: `strength_score`, unit `"score"` (0–100);
  - reach: `smoothness`, unit `"mm"` (lower is smoother);
  - tap: `taps_per_sec`, unit `"taps/s"`, the mean over the hands whose tap test is `done`.
- `baseline_pct`: percent difference from the mean of earlier done tests of that type. It is `null` while `baseline_n < 3` ("building your baseline").
- `status`:
  - `"done"`: `value` is set;
  - `"failed"`: tried but not recorded, `value` is `null`;
  - `"missing"`: no test of that type in the check, `value` is `null`.

  For tap, the card is `done` if either hand is done.
- 404 `not_found` if the check doesn't exist.

### `POST /api/checks/{check_id}/tests`

Body `StartTestRequest`:
```json
{ "type": "rest", "hand": "right" }
```
- Starts recording, except for `tap`, which only creates the test row (the browser records it).
- **Posture band:** `settings.posture_band` if set; otherwise the latest ToF height ± 30 mm.
- A recording older than 120 s is marked `failed` / `interrupted` before the new one starts.

Response **201** `TestStarted`:
```json
{ "test_id": 40 }
```
409 `test_active` if another test has been recording for less than 120 s. 404 if the check doesn't exist.

### `POST /api/tests/{test_id}/stop`

No body. Stops recording, saves the raw batches, and runs analysis. Response `TestOutcomeOut`:
```json
{ "test_id": 40, "status": "done", "fail_reason": null, "result": { "...": "ResultOut" } }
{ "test_id": 41, "status": "failed", "fail_reason": "sensor_disconnected", "result": null }
```
Analysis failures are **200 with `status: "failed"`**, never a 5xx. 409 `invalid_state` if the test isn't recording. During development, a test type whose analysis isn't built yet returns 501 `not_implemented`, and the test is stored as `failed` / `interrupted`.

### `POST /api/tests/{test_id}/mark`

No body. Marks a reach-attempt boundary at the current time. Response **204**, no body. 409 `invalid_state` if the test isn't recording.

### `POST /api/tests/{test_id}/tap-data`

Body `TapDataIn`:
```json
{
  "frames": [
    { "t_ms": 1234.5, "lm": [[0.51, 0.62], [0.48, 0.40], [0.47, 0.38], [0.50, 0.55]] },
    { "t_ms": 1267.9, "lm": null }
  ]
}
```
- `t_ms`: `performance.now()` in milliseconds. Only the differences matter.
- `lm`: the `[x, y]` normalized image coordinates of landmarks **0, 4, 8, 9**, in that order (exactly 4 pairs), or `null` when no hand was found.
- At most 10 000 frames.

Response `TestOutcomeOut`. 409 `invalid_state` if the test isn't a tap test or is already finished.

### `GET /api/doses`

Query: `from`, `to` (ISO-8601, optional). Response `DoseOut[]`, oldest first:
```json
[{ "id": 7, "taken_at": "2026-11-14T13:02:00Z", "label": null }]
```

### `GET /api/insights/dose-response`

Query: `days` (1–365, default 14). The window is the last `days` **local calendar days**, including today (from local midnight `days − 1` days ago until now). All `/api/insights/*` endpoints and `/api/report` use it. Response `DoseResponseOut`:
```json
{
  "bins": [{ "start_h": 0.0, "mean": 0.071, "count": 6 }, { "start_h": 0.5, "mean": 0.065, "count": 8 }],
  "returns_after_h": 3.0,
  "doses": [{ "id": 7, "taken_at": "2026-11-14T13:02:00Z", "label": null }]
}
```
- `bins`: rest-test `strength_ms2` (m/s²), binned by hours since dose. Bins are 0.5 h wide, cover 0–6 h, and empty bins are omitted. `start_h` is the bin's lower edge in hours.
- `returns_after_h`: the first bin at ≥ 1 h whose mean exceeds the overall median, needing at least 3 samples, or `null`.

### `GET /api/insights/profile`

Query: `days`. Response `ProfileRow[]`, one per test type, in the order rest, posture, reach, tap:
```json
[{ "test_type": "rest", "first_week": 38.2, "first_n": 24, "current": 41.0, "current_n": 10 }]
```
- The metric per test is the same as the Results card: `strength_score`, `smoothness` (mm) or `taps_per_sec`.
- `first_week` covers the 7 days from the first check. `current` covers the last 3 days.
- A value is `null` when its count is 0.

### `GET /api/insights/summary`

Query: `days`. Response `InsightsSummary`:
```json
{
  "checks_completed": 47,
  "streak_days": 14,
  "returns_after_h": 3.0,
  "daily": [{ "date": "2026-11-14", "mean_rest": 0.18, "count": 4 }]
}
```
- `streak_days`: consecutive local calendar days with at least one completed check, ending today (or yesterday, if there's no check yet today). It counts back through all history and isn't limited by `days`.
- `daily`: one entry per local day in the window, oldest first. `mean_rest` is the mean rest `strength_ms2`, or `null` on days with no rest result.

### `GET /api/report`

Query: `days` (default 14). Response `ReportOut`, which reuses the insight shapes:
```json
{
  "period": { "start": "2026-10-31T15:00:00Z", "end": "2026-11-14T15:00:00Z" },
  "checks_completed": 47,
  "dose_response": [{ "start_h": 0.0, "mean": 0.071, "count": 6 }],
  "returns_after_h": 3.0,
  "profile": [{ "test_type": "rest", "first_week": 38.2, "first_n": 24, "current": 41.0, "current_n": 10 }],
  "daily": [{ "date": "2026-11-14", "mean_rest": 0.18, "count": 4 }],
  "generated_at": "2026-11-14T15:00:00Z"
}
```

### `GET /api/settings`

Response `SettingsModel`: the defaults merged with the stored values.
```json
{ "dose_times": ["08:00", "13:00", "18:00"], "reminder_times": [], "tested_hand": "right", "posture_band": null }
```
- `dose_times` and `reminder_times`: local `"HH:MM"` (24 h).
- `posture_band`: `[low_mm, high_mm]` with 0 ≤ low < high ≤ 2000, or `null` for "start height ± 30 mm".

### `PUT /api/settings`

Body `SettingsUpdate`: any subset of the `SettingsModel` fields.
- Omitted fields keep their stored value.
- Sending `"posture_band": null` explicitly clears the band.
- A bad time format gives 422 `validation_error`.

Response: the full `SettingsModel` after the update.

### `POST /api/led`

Body `LedRequest`:
```json
{ "command": "countdown", "value": 7 }
```
- `value` is used by `countdown` (the number to show, 0–30) and by `recording` (`1` = on, `0` = off). Other commands ignore it.
- Response **204**.
- On the simulator and replay sources it's a no-op. LED failures are logged and never returned as errors.

---

## WebSocket `/ws`

### `WS /ws`

Server → client only. Every message is a JSON object with a `type` field. Timestamps are epoch seconds.

| `type` | Rate | Shape |
|---|---|---|
| `imu` | ~10/s | `{ "type": "imu", "t0": 1731600000.123, "fs": 100.0, "samples": [[ax, ay, az, gx, gy, gz], ...] }` |
| `tof` | ~10/s | `{ "type": "tof", "t0": 1731600000.123, "fs": 40.0, "t": [0.0, 0.026, 0.049, ...], "samples_mm": [212.0, 211.0, ...] }` |
| `spectrum` | ~4/s, only while a rest or posture test is recording | `{ "type": "spectrum", "freqs": [0.0, 0.25, ...], "psd": [...], "peak_hz": 5.0 }` |
| `position` | ~10/s, only while a posture test is recording | `{ "type": "position", "tof_mm": 214.0, "in_band": true, "band": [170.0, 230.0], "valid_seconds": 12.5 }` |
| `status` | 1/s while recording, and when recording starts or stops | `{ "type": "status", "recording": true, "test_id": 40, "test_type": "rest", "seconds_left": null }` |
| `source` | On connect, then whenever the source health changes | `{ "type": "source", "sensor_source": "board", "connected": true, "sensors": { "movement": true, "distance": true }, "imu_hz": 100.2, "tof_hz": 41.0 }` |

Field notes:
- **`imu`:**
  - Sample `i` is at time `t0 + i / fs`. `fs` is the batch's effective rate, measured from its timestamps; it is never assumed to be 100.
  - `samples` rows are acceleration in m/s² then gyroscope in deg/s.
- **`tof`:**
  - Sample `i` is at **`t0 + t[i]`**. `t` holds per-sample offsets in seconds (`t[0] == 0`), the same length as `samples_mm`.
  - Invalid readings are dropped, so the spacing can be uneven. **Never rebuild ToF times from `fs`.** `fs` is the batch's effective rate, kept for display only.
- **`spectrum`:**
  - Computed over the last ≤ 8 s of the recording. `freqs` are in Hz, up to 15 Hz.
  - `psd` is in (m/s²)²/Hz, summed over the axes.
  - `peak_hz` is `null` when no clear tremor is detected.
- **`position`:**
  - `band` is `[low_mm, high_mm]`. When `tof_mm < band[0]` the hand is too low; when `tof_mm > band[1]` it is too high.
  - `valid_seconds` is the in-band time accumulated so far.
  - `tof_mm` is `null` when the latest reading is invalid.
- **`status`:** the frontend owns test timing, so `seconds_left` is always `null`. The field is kept for PRD compatibility. `test_id` and `test_type` are `null` when not recording.
- **`source`:** `connected: false` means the board link dropped. Show the disconnect message and offer Retry.

Additions beyond the PRD shapes: `tof.fs`, `tof.t`, `position.band`, `position.valid_seconds`, `status.test_id`, `status.test_type`, and the whole `source` message.

---

## Result payloads

`ResultOut`: every field is nullable, and only the fields for the test's type are set.

| Field | Unit | Set for |
|---|---|---|
| `peak_hz` | Hz (`null` when no clear tremor) | rest, posture |
| `strength_ms2` | m/s² (3–12 Hz band RMS) | rest, posture |
| `strength_score` | 0–100 | rest, posture |
| `tremor_detected` | bool | rest, posture |
| `valid_seconds` | s analyzed | rest, posture |
| `smoothness` | mm (residual RMS; lower is smoother) | reach |
| `wobble_ratio` | unitless (> 1.5 = more wobble near the end) | reach |
| `taps_per_sec` | taps/s | tap |
| `tap_amplitude` | unitless (thumb–index distance ÷ hand size) | tap |
| `amplitude_decrement` | fraction (−0.3 = 30% smaller by the end) | tap |
| `rhythm_cv` | unitless (lower is steadier) | tap |
| `details` | object, see below | all |

`details` per test type (curves are downsampled for display):
- **rest / posture:** `{ "freqs": number[], "psd": number[] }`. Bins up to 15 Hz, 4 significant figures.
- **reach:** `{ "attempts": [{ "t": number[], "mm": number[], "residual": number[] }] }`. At most 200 points per attempt; `t` is seconds from the attempt start.
- **tap:** `{ "t": number[], "signal": number[], "peaks": number[] }`. `t` is seconds from the first frame, and `peaks` are indices into `signal`.

---

## Sensor source protocol

All sensor data enters the backend through `SensorSource` (`backend/tremorlab/sources/base.py`). `SENSOR_SOURCE=sim|board|replay` selects the implementation. Nothing downstream knows which one is active.

```python
LedCommand = Literal["countdown", "hold", "check", "idle", "clear", "recording"]

@dataclass(frozen=True)
class ImuBatch:      # t (N,) epoch s; acc (N, 3) m/s²; gyro (N, 3) deg/s
    t: NDArray[np.float64]; acc: NDArray[np.float64]; gyro: NDArray[np.float64]

@dataclass(frozen=True)
class TofBatch:      # t (N,) epoch s; mm (N,) — NaN when invalid
    t: NDArray[np.float64]; mm: NDArray[np.float64]

@dataclass(frozen=True)
class SourceStatus:  # link or sensor state change
    connected: bool; sensors: dict[str, bool] = {}; message: str | None = None

Batch = ImuBatch | TofBatch | SourceStatus

@dataclass(frozen=True)
class SourceHealth:
    connected: bool; sensors_detected: dict[str, bool]; imu_hz: float | None; tof_hz: float | None

class SensorSource(Protocol):
    name: str
    async def start(self) -> None
    async def stop(self) -> None
    def batches(self) -> AsyncIterator[Batch]
    async def led(self, command: LedCommand, value: int | None) -> None
    def health(self) -> SourceHealth
```

- `sensors` / `sensors_detected` keys: `"movement"`, `"distance"`.
- Rates are always measured from timestamps, never assumed.
- `make_source(config)` dispatches:
  - `sim` → `SimulatedSource(config.sim)`
  - `board` → `BoardSource(config.board_host, config.board_port)`
  - `replay` → `make_replay_source(config)`

---

## Board wire protocol (NDJSON over TCP 7700)

- The relay on the UNO Q listens on `0.0.0.0:7700` and accepts one client at a time; a new connection replaces the old one. The Mac reaches it through `adb forward tcp:7700 tcp:7700`.
- Each message is one JSON object followed by `\n`. Malformed lines are ignored.

**Board → Mac:**

```json
{"k":"imu","d":[t_us, ax_mg, ay_mg, az_mg, gx_mdps, gy_mdps, gz_mdps, t_us, ...]}
{"k":"tof","d":[t_us, mm, t_us, mm, ...]}
{"k":"status","d":["ok", imu_count, tof_count, nan_count]}
```
- **`imu`:** a flat list of ints, 7 per sample.
  - `t_us` is the 32-bit `micros()` value, sent as a **signed int32** (the Mac masks with `& 0xFFFFFFFF`). It wraps about every 71.6 min, and the Mac unwraps it.
  - Acceleration is in milli-g; the Mac converts with m/s² = mg × 9.80665 / 1000.
  - Gyroscope is in milli-deg/s; the Mac converts with deg/s = mdps / 1000.
- **`tof`:** `mm` is an integer distance. Invalid (NaN) readings are skipped on the board and counted in `nan_count`.
- **`status`:** sent once a second. The first element is `"ok"`, `"movement_missing"`, `"distance_missing"` or `"both_missing"`. The counts cover the last second.
- **Batching:** one sample per message, because `notify` blocks the MCU while it sends (measured; see `docs/hardware-notes.md`). Receivers must accept any whole number of samples per line.
- **Ordering:** lines can arrive slightly out of order. Order samples by `t_us`, never by arrival.

**Mac → Board:**

```json
{"k":"led","cmd":"countdown","value":7}
```
- `cmd` is a `LedCommand`. `value` is an int; send `0` when unused.

**Clock mapping (Mac side):** `mac_t = mac_time_at_first_batch + (mcu_s − mcu_s_at_first_batch)`. Only the MCU clock spaces samples. The link counts as disconnected after 1 s with no data. Reconnect backoff is 0.5 s, doubling to a maximum of 5 s.
