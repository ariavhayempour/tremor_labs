# Hardware notes (Arduino UNO Q)

Measured and observed facts about the board, the toolchain and the link to the Mac. Code that touches hardware relies only on what is recorded here or marked verified in the design spec.

## Mac toolchain (observed 2026-11-14)

| Item | Value | How found |
|---|---|---|
| App Lab app | `/Applications/Arduino App Lab.app` | installed |
| App Lab workspace (Mac) | `~/Library/Application Support/arduino_applab_workspace/` (bundled arduino-cli config, libraries, Python/TS tooling) | filesystem |
| Bundled adb | `~/Library/Arduino15/packages/arduino/tools/adb/32.0.0/adb` (adb 1.0.41, 32.0.0-8006631) | filesystem; `adb version` |
| adb on PATH | not installed (`brew install android-platform-tools` is optional, since the bundled adb works) | `which adb` |
| Modulino / RouterBridge / LED_Matrix libraries on the Mac | not present yet; App Lab fetches them when a sketch first compiles | `find ~/Library/Arduino15` |
| App Lab apps folder | **unknown until a board is connected** (expected on the board under `~/ArduinoApps`, per the official examples) | — |

To use the bundled adb without Homebrew, put this in your shell:

```bash
export PATH="$HOME/Library/Arduino15/packages/arduino/tools/adb/32.0.0:$PATH"
```

## Setup: HUMAN ACTION REQUIRED

### 1. App Lab and Blink
1. App Lab is already installed. Open it.
2. Plug the UNO Q into the Mac with a USB-C **data** cable (a charge-only cable shows nothing), on a port that can supply 5 V / 3 A.
3. In App Lab, select the UNO Q. Accept any updates, and **don't unplug while it updates**. If asked for credentials, use the ones on the setup sheet. **Skip Wi-Fi.**
4. Open Examples → Blink → Run.
5. **Success signal:** the onboard LED blinks.

### 2. adb
1. Run `adb devices` (with the PATH export above, or after `brew install android-platform-tools`).
2. **Success signal:** exactly one device listed with state `device`. If it shows `unauthorized`, re-plug the board and accept the prompt.
3. Run `adb shell uname -a`. **Success signal:** a Linux kernel line.

## Results

| Check | Result |
|---|---|
| Blink | **not run**: App Lab wants the board on Wi-Fi first, and Wi-Fi is skipped |
| `adb devices` | one device, state `device` (bundled adb) |
| `adb shell uname -a` | `Linux 6.16.7 ... aarch64 GNU/Linux` (Debian 13 trixie) |
| Board user / home | `arduino` / `/home/arduino` (groups include `docker`, `dialout`, `gpiod`) |
| Apps folder on the board | `/home/arduino/ArduinoApps/` (exists, empty) |
| Board Python | 3.13.5 (host); apps run in Docker |
| Cached app images | `ghcr.io/arduino/app-bricks/python-apps-base:0.5.0`, `ei-models-runner:0.5.0`, `influxdb:2.7`, so the Python side should run offline |
| Board network | `wlan0` down, `docker0` 172.17.0.1/16 (down until a container runs), no default route |
| Board-side CLI | `arduino-app-cli` v0.6.6, with `app new/start/stop/restart/logs/list/ps/monitor`; a daemon listens on 127.0.0.1:8800 |
| Other listeners | 127.0.0.1:7500, 127.0.0.1:37735 (unidentified) |
| adb stability | the device dropped to `offline` mid-session (cause unknown; App Lab may also be driving the board) |

## Working without Wi-Fi

App Lab's Mac UI wants Wi-Fi before it will run an app. The board itself has everything an app needs: the cached base image, and `arduino-app-cli` to create, start and stop apps. The plan is to drive apps through `adb shell arduino-app-cli app ...` from the Mac, using only the commands and flags its `--help` lists. Whether the board can compile and flash a sketch offline is still unverified.

### App Lab offline mode (observed in App Lab 0.12.0)

- Without internet, App Lab connects over USB and offers **Continue offline**. Unavailable offline: updates and downloads, AI model import, **sketch libraries**, and apps that need internet.
- **Board core:** `arduino:zephyr` 0.51.0, FQBN `arduino:zephyr:unoq`.
- **Libraries bundled with the core** (no download needed): `Arduino_LED_Matrix`, `Arduino_RouterBridge`, `Arduino_RPCLite`, `Wire`, `SPI`, `WiFi`, `Ethernet`, `SocketWrapper`, `Camera`, `ea_malloc`, `Zephyr_SDRAM`.
- **Not present on the board:** `Arduino_Modulino` and its sensor drivers, plus `MsgPack 0.4.2`, `DebugLog 0.8.4`, `ArxContainer 0.7.0` and `ArxTypeTraits 0.3.1`. The last four are listed by every new app's `sketch.yaml` (from `arduino-app-cli app new`).
- **Template app** (`arduino-app-cli app new probe-template`):
  - `app.yaml` has `name`, `description`, `icon`, `ports: []`, `bricks: []`;
  - `python/main.py` has a `main()` hello world;
  - `sketch/sketch.ino` has empty `setup`/`loop`;
  - `sketch/sketch.yaml` has profile `default`, fqbn `arduino:zephyr:unoq`, platform `arduino:zephyr`, and the four libraries above.

## Library facts (Arduino_Modulino 0.7.0 source, `src/Modulino.h`)

- Official examples pin `Arduino_Modulino (0.7.0)` with these dependencies:
  - `ArduinoGraphics 1.1.4`
  - `Arduino_HS300x 1.0.0`
  - `Arduino_LPS22HB 1.0.2`
  - `Arduino_LSM6DSOX 1.1.2`
  - `Arduino_LTR381RGB 1.0.0`
  - `STM32duino VL53L4CD 1.0.5`
  - `STM32duino VL53L4ED 1.0.1`

  Bridge-only examples list no libraries at all.
- **`ModulinoMovement`:**
  - `update()` reads the accelerometer and gyroscope every time it's called, whether or not new data is ready.
  - `available()` is true when both have new samples, so use it to count real samples.
  - `getX/Y/Z()` return g, and `getRoll/Pitch/Yaw()` return deg/s.
- **`ModulinoDistance`:**
  - `begin()` sets a 20 ms timing budget and starts continuous ranging, so at most about 50 Hz.
  - **Caveat:** `available()` returns true whenever the last stored result is valid, even if no new measurement arrived since the previous call. Counting `available()` calls overstates the ToF rate, and `get()` repeats the same reading. Sample rates must come from new-measurement detection, never from loop counts.
  - An invalid range status gives `NAN`.

## Driving apps over adb (no App Lab UI)

```bash
export PATH="$HOME/Library/Arduino15/packages/arduino/tools/adb/32.0.0:$PATH"
adb push board/probes/<name> /home/arduino/ArduinoApps/tremor-probe-<name>
adb shell 'export TMPDIR=/tmp; arduino-app-cli app start /home/arduino/ArduinoApps/tremor-probe-<name>'
adb shell 'export TMPDIR=/tmp; arduino-app-cli app logs /home/arduino/ArduinoApps/tremor-probe-<name>'
adb shell 'export TMPDIR=/tmp; arduino-app-cli app stop /home/arduino/ArduinoApps/tremor-probe-<name>'
```

- **`TMPDIR` must be set.** `adb shell` sets `TMPDIR=/data/local/tmp`, an Android path that doesn't exist here, and `app start` fails with `Stat /Data/Local/Tmp: No Such File Or Directory`.
- **Offline builds:**
  - A sketch with **no** Bridge (e.g. the LED probe) compiles, flashes and starts with no internet.
  - Any sketch that includes `Arduino_RouterBridge` fails offline with `fatal error: MsgPack.h: No such file or directory` until `MsgPack` (and the other helper libraries) are downloaded once.
- **Board clock:** the board's clock reads 2025-09-09 offline (no NTP). The backend never uses board wall time, only MCU `micros()` deltas mapped to Mac time.

## Probe results

### LEDs (`board/probes/leds`), observed 2026-11-14
- **LED matrix:** `matrix.begin()`, `setGrayscaleBits(3)` and `draw(uint8_t[104])` work. 3×5 digits at column offset 5, rows 1–5, display correctly and upright, and the 8×13 checkmark bitmap is correct.
- **RGB LED3 is active-low.** Driving one pin HIGH lit the other two colors (R HIGH → cyan, G HIGH → magenta, B HIGH → yellow), and all LOW → white.
  - To show a single color, set that pin LOW and the others HIGH.
  - All HIGH = off.
  - Green while streaming = `R=HIGH, G=LOW, B=HIGH`.
- LED4 is assumed to be wired the same way (same overlay style). Not tested.

### Link + sensors (`board/probes/sensors`), measured 2026-11-14

- **Transport works: the USB-only design is confirmed.**
  - `ports: [7700]` in `app.yaml` publishes the app container's port on the board's `0.0.0.0:7700` (and `[::]:7700`).
  - `adb forward tcp:7700 tcp:7700` reaches it from the Mac.
  - Inside the container the client appears as `172.19.0.1` (the Docker bridge).
  - No fallback transport is needed.
- **App runtime:** apps run Python 3.13.9 in a venv inside the container (`.cache/.venv`). `print` and `Logger` output shows in `arduino-app-cli app logs`.
- **Rates** (Movement + Distance daisy-chained on Wire1; hand ~20 cm above the ToF):

| Measure | Value |
|---|---|
| IMU new samples (`movement.available()`) | **106–107 Hz** |
| ToF new readings (changed value) | **38–44 Hz** |
| ToF `available()` true per second | 254–256 (= loop rate, so the stale-repeat caveat is confirmed) |
| Invalid ToF polls with the hand in view | 0 |
| `loop()` passes per second, polling both sensors every pass | ~255 (≈ 4 ms per pass) |

- **Implications for the production sketch:**
  - Polling both sensors on I2C every pass costs about 4 ms. Schedule the IMU read with `micros()` at 100 Hz, and poll the ToF no faster than about every 20 ms, so the IMU timestamps don't pick up up to 4 ms of jitter.
  - Timestamp each IMU sample at the moment it's read.
- **Delivery timing:** the 1/s `rates` notifies reached the Mac in bursts (sometimes 2 in one second, then none). The Bridge → Python → TCP path may buffer for up to about 1 s. See the throughput results for latency at batch sizes.

### Getting libraries onto an offline board

The app service (`arduino-app-cli.service`) resolves DNS through whatever `/etc/resolv.conf` held when it started. If it started before Wi-Fi was up, every library download fails with `lookup downloads.arduino.cc on [::1]:53 ... connection refused`. Restarting the service needs sudo. The workaround that needs no sudo, run as the `arduino` user while online:

```bash
adb shell 'export TMPDIR=/tmp; arduino-cli lib update-index; arduino-cli lib download "Arduino_Modulino@0.7.0" ...'
```

The build then installs from `~/.arduino15/staging/libraries/` ("already downloaded"). Notes:
- The board's original index only knew Modulino up to 0.6.1. After `update-index`, 0.7.0–0.9.1 are listed.
- Cached on the board as of 2026-11-14:
  - `MsgPack 0.4.2`
  - `DebugLog 0.8.4`
  - `ArxContainer 0.7.0`
  - `ArxTypeTraits 0.3.1`
  - `Arduino_Modulino 0.7.0`
  - `ArduinoGraphics 1.1.4`
  - `Arduino_HS300x 1.0.0`
  - `Arduino_LPS22HB 1.0.2`
  - `Arduino_LSM6DSOX 1.1.2`
  - `Arduino_LTR381RGB 1.0.0`
  - `STM32duino VL53L4CD 1.0.5`
  - `STM32duino VL53L4ED 1.0.1`
- This board's tooling (`arduino-app-cli` 0.6.6) rejects the `- dependency: X (v)` entries used by the newer official examples. List every library as a plain `- X (v)` entry.
- **Bridge serial:** `arduino-router` talks to the MCU at **115200 baud** on `/dev/ttyHS1`.

### Throughput (`board/probes/throughput`), measured 2026-11-14

`std::vector<int>` passed to `Bridge.notify` at 10 messages/s, 3 s per size (30 expected), values ≥ 100000 so each int needs 5 bytes in MessagePack:

| Ints per message | Received per 3 s phase (2–3 cycles) |
|---|---|
| 10 | 30, 24* |
| 35 | 32*, 35* |
| **70** | **30, 29, 30** |
| 140 | 30, 30, 30 |
| 280 | 30, 30, 30 |
| 560 | 29, 31* |

\* Counts off by up to 5 at a size change: messages from the previous phase arriving after the next phase's start notify (`bad_len` matches the surplus).

- **Largest size delivered in full: 560 ints at 10 Hz.** That is about 28 kB/s, well above what the nominal 115200 baud would allow, so the serial baud isn't the limit. Production needs about 70 IMU ints + about 8 ToF ints per 100 ms, a margin of about 7×. **No fallback (50 ms flush or 50 Hz) is needed.**
- **Delivery is bursty:** messages can arrive up to about 0.5 s late, in clumps. The backend must place samples by MCU timestamps, never by arrival time. End-to-end latency against the PRD's < 200 ms target is still to be measured at M2.
- `arduino-app-cli app start` does **not** replace a running app. Stop the running one first (`app stop <path>`).
- `arduino-app-cli app ps` panics with `not implemented` in v0.6.6.

## Board network state

- After the probes the board was taken off Wi-Fi again: `nmcli con down tremor-hotspot`, with autoconnect disabled.
- To get online again for new library downloads: `adb shell nmcli con up tremor-hotspot`, then `arduino-cli lib download ...` as described above.

## Production app (`board/tremorlab`), measured 2026-11-14

- **`Bridge.notify` blocks the sketch while the serial link sends** (about 115200 baud).
  - A 70-int batch every 100 ms stalled `loop()` for about 26 ms. The IMU lost about 12 samples/s (88/s, gaps up to 26 ms).
  - **Fix:** one sample per message (`imu` = 7 ints, `tof` = 2 ints). Measured: **IMU 100.0/s and ToF 50.0/s exactly** (status counts 100/50 every second). Sorted by MCU time, IMU spacing is 9.4–10.7 ms (std 0.55 ms), with no duplicates.
- **Out-of-order delivery:** the board's Python side handles Bridge callbacks on several threads, so about 0.5% of messages arrive one position late. `BoardSource` reorders them by MCU timestamp inside a short window. Never trust arrival order.
- **Build quirks on `arduino:zephyr` 0.51.0:**
  - `std::vector::reserve()` fails to link (`multiple definition of std::__throw_length_error`, which clashes with the core's `abi.cpp`). Don't call it; `push_back`, `clear` and `assign` link fine.
  - `lroundf` (libm) is not linked. Round by hand.
- **Bridge callbacks on the MCU** (`Bridge.provide`) run on another thread. They only record the command; `loop()` draws on the matrix. This follows the official matrix examples, none of which uses `provide_safe`.
- **LED cue sequence verified by eye (2026-11-14):** countdown 7 and 23, hold, recording 1 (blue), check, recording 0 (green), idle (breathing), clear.
- **Status is sent as an int code** (0 ok, 1 movement_missing, 2 distance_missing, 3 both_missing). The relay maps it to the contract string, so the sketch only ever sends ints, which is what the probes proved.
- **ToF is sampled at a fixed 20 ms** (50/s) with `available()`/`get()`. A reading can repeat the previous mm value (the stale-result caveat). Accepted: the repeats are real "latest reading" samples, spaced 20 ms apart.

## Recovery: Bridge router stuck

- **Symptom:** an app starts, the relay accepts the Mac's TCP connection, but **no** imu/tof/status lines arrive, not even from a probe that worked before.
- **Router logs:** `journalctl -u arduino-router.service` shows `ERROR Error in connection err="invalid packet, expected array, got: int8"` around flashes. Its serial stream to the MCU (`/dev/ttyHS1`) had lost sync.
- **Fix:** power-cycle the board (unplug USB, wait 5 s, re-plug, wait about 40 s) or `sudo systemctl restart arduino-router.service`.
- The `invalid packet` line appears on every flash and is usually harmless. The stuck state was seen once, after many flashes in a row.
