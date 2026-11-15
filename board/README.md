# Board apps

- `tremorlab/` is the production app. The sketch samples Modulino Movement (100 Hz) and Distance (50 Hz) and drives the LED matrix and RGB LED3. The Python side relays NDJSON on TCP 7700 (wire protocol: `docs/contracts.md`).
- `probes/` holds the throwaway hardware probes. Their results are in `docs/hardware-notes.md`.

## Load and run without App Lab (USB only)

```bash
export PATH="$HOME/Library/Arduino15/packages/arduino/tools/adb/32.0.0:$PATH"
adb push board/tremorlab /home/arduino/ArduinoApps/tremorlab
adb shell 'export TMPDIR=/tmp; arduino-app-cli app start /home/arduino/ArduinoApps/tremorlab'
make board-link                      # adb forward tcp:7700 tcp:7700
```

- **Success signal:** `✓ App "tremorlab" started successfully`, LED3 green, and the matrix blank.
- `uv run --project backend python scripts/probe_client.py --quiet` prints about `imu=100/s, tof=50/s, status=1/s`.
- **Stop an app before starting another** (`arduino-app-cli app stop <path>`); `start` doesn't replace a running app.
- `TMPDIR=/tmp` is required under `adb shell`.

## Load with App Lab

Use this if you prefer the UI. Copy `board/tremorlab` into the board's apps folder, open it in App Lab and click Run. Quit App Lab before using adb from a terminal, because the two fight over the USB link.

## Libraries

The sketch needs the libraries pinned in `tremorlab/sketch/sketch.yaml`. They are cached on the board already. On a fresh board, see "Getting libraries onto an offline board" in `docs/hardware-notes.md` (one short Wi-Fi session).

## LED cues

Send these from the Mac as `{"k":"led","cmd":...,"value":n}`, or through `POST /api/led`:

| Command | Matrix | RGB LED3 |
|---|---|---|
| `countdown n` | number 0–99 | unchanged |
| `hold` | hand icon | unchanged |
| `check` | checkmark | unchanged |
| `idle` | breathing diamond | unchanged |
| `clear` | blank | unchanged |
| `recording 1` / `recording 0` | unchanged | blue / green |
| (sensor missing) | — | red |

## If no data arrives

See "Recovery: Bridge router stuck" in `docs/hardware-notes.md`. The usual fix is a power cycle.
