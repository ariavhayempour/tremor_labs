# Signal analysis

Pure functions in `backend/tremorlab/analysis/`: no I/O, no clock, no DB. Inputs are SI:
time in epoch seconds, acceleration in m/s², distance in mm. Every tuning value is a
module-level constant. This page lists every constant and explains how to tune it.

Failures raise `AnalysisError(code)` (`errors.py`). The session stores a `failed` test with
that `fail_reason`. A failure is never returned as a 500.

## Sampling (`sampling.py`)

The rate is never assumed. It is always measured from timestamps.

| Constant | Value | Units | Meaning |
|---|---|---|---|
| `TRIM_SECONDS` | 2.0 | s | Dropped from each end of a rest recording (settling, button press) |
| `RESAMPLE_CV_LIMIT` | 0.05 | ratio | If the coefficient of variation of Δt is above this, the data is resampled onto a uniform grid |
| `GRID_EPS` | 1e-9 | samples | Rounding slack so a grid point that lands exactly on the last timestamp is kept |

- `effective_fs(t)` is the median of `1/Δt` in Hz. It ignores non-positive Δt (duplicate
  timestamps). It raises `insufficient_valid_data` when there are fewer than 2 samples or the
  timestamps don't advance.
- `trim_edges(t, x, s)` keeps the samples where `t[0]+s ≤ t ≤ t[-1]−s`. A recording shorter
  than `2s` comes back empty.
- `needs_resample(t)` is true when `std(Δt)/mean(Δt) > RESAMPLE_CV_LIMIT`. With ±1 ms jitter at
  ~97 Hz the CV is about 8%, so that stream is resampled. A clean 100 Hz stream is not.
- `resample_uniform(t, x, fs)` linearly interpolates each column onto `t[0] + k/fs`. The grid ends
  at or before `t[-1]`, so nothing is extrapolated. It interpolates on `t − t[0]` to keep
  precision with epoch-second timestamps.
- `max_gap(t)` is the largest Δt in seconds. The session uses it to detect a dropped link: a gap
  over 1 s means `sensor_disconnected`.

## Rest tremor (`tremor.py`)

### Pipeline

`analyze_tremor(t, acc, *, trim=True)`:

1. Drop any row whose timestamp or axis value is NaN or inf.
2. If `trim` is set, drop `TRIM_SECONDS` from each end. The live spectrum calls the function
   with `trim=False` on the last ≤ 8 s.
3. Compute `valid_seconds = N / fs`. If it is under `MIN_SECONDS`, raise
   `insufficient_valid_data`. The check allows half a sample of slack because float rounding of
   epoch timestamps moves the measured rate by about 1e-6.
4. Compute the spectrum with `tremor_spectrum(t, acc)`:
   - Measure `fs`. If `needs_resample` is true, resample onto a uniform grid at `fs`.
   - High-pass each axis to remove gravity and slow drift. The filter is a Butterworth of order
     `HP_ORDER` at `HP_CUTOFF_HZ`, applied zero-phase with `sosfiltfilt` (the
     second-order-sections form of `filtfilt`).
   - Compute a Welch PSD per axis and sum the three axes. Settings: Hann window,
     `nperseg = round(WELCH_WINDOW_S·fs)` (capped at N), `noverlap = nperseg // 2`, density
     scaling in (m/s²)²/Hz. At any rate the bin spacing is `1/WELCH_WINDOW_S` = 0.25 Hz.
5. Summarize the summed PSD over `BAND_HZ`:
   - **Strength:** `strength_ms2 = sqrt(Σ PSD[band] · Δf)` in m/s². This is the RMS of the
     acceleration vector band-passed to 3–12 Hz, computed in the frequency domain (Parseval's
     theorem), so rest and posture share one definition. A sinusoid of amplitude `A` on one axis
     contributes `A/√2`. With the simulator's axis weights 0.6/0.6/0.5 and `A = 0.3`, the result
     is `A·√0.97/√2 ≈ 0.209` m/s².
   - **Peak:** the bin with the largest PSD inside `BAND_HZ`. It is refined by parabolic
     interpolation on log PSD over that bin and its two neighbors, with the shift clamped to
     ±`PEAK_MAX_SHIFT_BINS`. Synthetic sines read within about 0.01 Hz.
   - **Detection:** a tremor is detected when `PSD[peak] ≥ PEAK_TO_MEDIAN_MIN · median(PSD[band])`
     **and** `strength_ms2 ≥ RMS_MIN_MS2`. Otherwise `peak_hz` is `None` ("no clear tremor").
   - **Score:** see the next section.
6. Return `freqs` and `psd` for display.

### Score

```
score = clamp(100 · log10(rms / SCORE_FLOOR_MS2) / log10(SCORE_CEIL_MS2 / SCORE_FLOOR_MS2), 0, 100)
```

The score is logarithmic because tremor amplitude spans orders of magnitude. 0.05 m/s² (a real
still hand) maps to 0 and 5.0 m/s² maps to 100, so the scale is exactly two decades: **50 points
per decade**, about 15 points per doubling. Examples: 0.057 (still hand) → 3, 0.1 → 15,
0.14 (detection gate) → 22, 0.209 (simulator default) → 31, 0.5 → 50, 1.0 → 65, 2.0 → 80.

### Constants

| Constant | Value | Units | Meaning |
|---|---|---|---|
| `HP_CUTOFF_HZ` | 2.0 | Hz | High-pass cutoff (removes gravity, drift, voluntary movement) |
| `HP_ORDER` | 4 | — | Butterworth order (the zero-phase filter applies it twice) |
| `BAND_HZ` | (3.0, 12.0) | Hz | Tremor band for the peak search, the strength and the noise floor |
| `WELCH_WINDOW_S` | 4.0 | s | Welch segment length; gives 0.25 Hz resolution |
| `PEAK_TO_MEDIAN_MIN` | 6.0 | ratio | Peak PSD ÷ in-band median PSD needed to call a tremor |
| `RMS_MIN_MS2` | 0.14 | m/s² | Band RMS needed to call a tremor (tuned on a real still hand) |
| `SCORE_FLOOR_MS2` | 0.05 | m/s² | RMS that maps to a score of 0 (about a real still hand) |
| `SCORE_CEIL_MS2` | 5.0 | m/s² | RMS that maps to a score of 100 |
| `MIN_SECONDS` | 4.0 | s | Least analyzable data, after the trim |
| `MIN_SPECTRUM_S` | 1.0 | s | Least data `tremor_spectrum` accepts when called on its own |
| `PEAK_MAX_SHIFT_BINS` | 0.5 | bins | Limit on the parabolic peak refinement |
| `DURATION_TOL_SAMPLES` | 0.5 | samples | Slack on the minimum-duration checks |

`tremor_spectrum` also raises `insufficient_valid_data` when `fs ≤ 2·BAND_HZ[1]` (24 Hz),
because the band can't be resolved below that rate.

### Behavior on synthetic data (simulator defaults: noise 0.02 m/s² per axis, 100 Hz)

| Case | Peak ÷ median | Band RMS | Detected |
|---|---|---|---|
| Still hand, 26 s analyzed | 1.3–1.6 | ~0.0145 m/s² | no |
| Still hand, 8 s live window | ≤ 3.1 (500 seeds) | ~0.0145 | no |
| Still hand, 4 s live window (one Welch segment) | up to 7.4, p99 5.0 | ~0.0145 | no, only because of the RMS gate |
| 5 Hz, amplitude 0.3 (simulator default) | ≫ 100 | 0.209 | yes (1.5× the gate) |
| 5 Hz, amplitude 0.205 | — | 0.144 | yes, 20/20 seeds (30 s and 4.5 s) |
| 5 Hz, amplitude 0.20 | — | 0.140 | about half the seeds: the edge |
| 5 Hz, amplitude 0.19 | — | 0.134 | no |

The **smallest reliably detected tremor** is a band RMS of 0.14 m/s²: a 5 Hz sine of amplitude
about 0.205 m/s² on the simulator's axis weights, or 0.20 m/s² (about 0.02 g) on a single axis.
Simulator noise sits at about 10% of `RMS_MIN_MS2`.

### Tuning on real data (Modulino Movement, 101 Hz measured)

Two 30 s board recordings live in `backend/tests/fixtures/hardware/`, checked by
`tests/analysis/test_real_fixtures.py` (skipped when the files are absent):

- `still_hand.npz`: sensor flat in an open palm, forearm resting.
- `metronome_5hz.npz`: shaking to a 300 BPM metronome.

Live windows are untrimmed (`trim=False`) and slide in 0.5 s steps. The full recording is
trimmed (26 s analyzed).

**Before tuning** (`RMS_MIN_MS2 = 0.02`, `SCORE_FLOOR_MS2 = 0.005`, `SCORE_CEIL_MS2 = 2.0`):

| | Still hand | Metronome |
|---|---|---|
| Full 26 s | not detected; ratio 4.84; RMS 0.057 m/s²; **score 41** | 5.07 Hz; ratio 41; RMS 6.72 m/s² |
| 8 s windows | **29/44 falsely detected**; ratio ≤ 18.8; RMS 0.042–0.083 | 44/44 detected, 4.93–5.32 Hz; ratio ≥ 17.3 |
| 4.5 s windows | **46/51 falsely detected**; ratio ≤ 39.7; RMS 0.035–0.091 | 51/51 detected, 4.58–5.59 Hz; ratio ≥ 10.4 |

The still-hand peaks sit at 8.7–10.5 Hz. That is normal **physiological tremor**, a real
signal and not a sensor artifact (only 0.7% of samples repeat). Its peak-to-median ratio (up to
39.7 on a 4.5 s window) overlaps the metronome's (down to 10.4), so the ratio cannot separate
them. Band RMS separates them by a factor of 54 (0.091 vs 4.93 m/s²).

**After tuning** (`RMS_MIN_MS2 = 0.14`, `SCORE_FLOOR_MS2 = 0.05`, `SCORE_CEIL_MS2 = 5.0`):

| | Still hand | Metronome |
|---|---|---|
| Full 26 s | not detected; RMS 0.057; **score 2.8** | 5.07 Hz; RMS 6.72; score 100 |
| 8 s windows | **0/44 detected**; score 0–10.9 | 44/44 detected, 4.93–5.32 Hz; score 100 |
| 4.5 s windows | **0/51 detected**; score 0–13.0 | 51/51 detected, 4.58–5.59 Hz; score ≥ 99.7 |

Why these values:

- **`RMS_MIN_MS2` 0.02 → 0.14.** The largest still-hand band RMS on any live window is
  0.091 m/s². The gate is set about 1.5× above it (0.137, rounded to 0.14). That is the lowest
  gate with that margin. The metronome's smallest window RMS is 35× above it.
- **`PEAK_TO_MEDIAN_MIN` stays 6.0.** The ratio overlaps between the two recordings, so raising
  it can't fix the still hand and would cost short-window tremor detections. It still rejects
  broadband movement that happens to exceed the RMS gate.
- **`SCORE_FLOOR_MS2` 0.005 → 0.05.** It now sits just under the still-hand RMS, so a still hand
  scores about 3 instead of 41.
- **`SCORE_CEIL_MS2` 2.0 → 5.0.** With the higher floor, a ceiling of 2.0 would leave only 1.6
  decades, and moderate tremor (a few m/s²) would saturate at 100. Tracking change across doses
  needs headroom at the top. 5.0 gives a clean two-decade scale. Vigorous voluntary shaking
  (6.7 m/s²) still saturates.

**Trade-off:** a mild tremor below 0.14 m/s² band RMS now reads "no clear tremor". Its strength
and score are still reported and stored, so a change over time remains visible. The gate is
tuned on one person's still hand. Enhanced physiological tremor (caffeine, fatigue, stress) can
be larger, so re-check it as more recordings come in. Posture (arm held out, unsupported)
shares this gate but has no still-hand recording yet, and outstretched physiological tremor is
usually larger than at rest. Record a posture still hand before trusting posture detections.

## Posture tremor (`posture.py`)

`analyze_posture(t_imu, acc, t_tof, mm, band)`:

1. **Valid ToF:** keep readings that are finite and inside `TOF_VALID_RANGE_MM` (inclusive).
   NaN, 0 and anything over 1300 mm (hand out of view) are dropped.
2. **Gate** (`in_band_mask`): linearly interpolate the valid ToF readings onto the IMU
   timestamps. An IMU sample is in band when the interpolated height is inside `band`
   (inclusive) **and** a valid ToF reading lies within `TOF_MATCH_MAX_S` of it. IMU samples in a
   gap of invalid ToF readings, or before or after the ToF span, are therefore out of band.
3. **Runs:** keep contiguous in-band runs of at least `MIN_RUN_S`. Run length and
   `valid_seconds` are sample count ÷ `effective_fs(t_imu)`.
4. If the total is under `MIN_VALID_S`, raise `insufficient_valid_data`.
5. Run `tremor_spectrum` on each run. Put each PSD on the longest run's frequency grid
   (`np.interp`), then average them weighted by run length.
6. Compute peak, strength, detection and score from the averaged PSD, exactly as for rest.

Posture applies **no** edge trim. The band gate already excludes the settling and button-press
periods. A 30 s recording with 8 s out of band yields 22 s of valid data.

`band_from_start(start_mm)` returns `start ± BAND_HALF_WIDTH_MM`. The session can instead pass
an absolute band from settings.

| Constant | Value | Units | Meaning |
|---|---|---|---|
| `BAND_HALF_WIDTH_MM` | 30.0 | mm | Half-width of the target band around the start height |
| `MIN_RUN_S` | 4.0 | s | Shortest in-band run used (one Welch window) |
| `MIN_VALID_S` | 20.0 | s | Least total in-band time |
| `TOF_VALID_RANGE_MM` | (20.0, 1300.0) | mm | ToF readings outside this range are invalid |
| `TOF_MATCH_MAX_S` | 0.2 | s | Farthest an IMU sample may be from a valid ToF reading |

## Reach (`reach.py`)

`analyze_reach(t, mm, marks)` takes ToF distance in mm and the attempt marks in epoch seconds.

1. **Clean** (`_clean`):
   - Drop out-of-view readings: NaN, ≤ 0, or above `TOF_MAX_MM`.
   - Sort by time.
   - Drop **stale repeats**, where a reading equals the previous one; the first is kept. The
     board polls the ToF every 20 ms (50/s) but gets only 38–44 new readings/s, so about one
     sample in five repeats the last value 20 ms late. Left in, a repeat looks like a jerk of
     up to ~4 mm in a fast reach.
   - The rate is never assumed. Timestamps may be uneven and have gaps.
2. **Windows:** marks split the recording into `[start, m1)`, `[m1, m2)`, `[m2, end]`. With no
   marks the whole recording is one window. A window without a usable descent is skipped.
3. **Descent** (`detect_descent`; indices refer to the cleaned series, inclusive):
   - Start: the first sample more than `START_DROP_MM` below the running maximum. Using the
     running maximum means a window that starts low and rises first still works.
   - End: the first sample under `END_MM`, **or** a stall. A stall is `STALL_S` with no new low
     more than `DECREASE_EPS_MM` below the running low; the end is then the last new low. The
     tolerance stops sensor-noise records from keeping a hover "decreasing". Descents slower
     than 4 mm/s count as stalled.
   - If neither end condition happens, the descent runs to the end of the window. It needs at
     least `SG_MIN_WINDOW` samples.
4. **Smoothing:**
   - Savitzky–Golay, order `SG_POLYORDER`. The window is the odd sample count nearest
     `SG_WINDOW_S·fs`, at least 5; a tie rounds up, so 40 Hz → 13 and 50 Hz → 15.
   - It runs on a uniform grid from the first to the last descent timestamp (SG assumes even
     spacing). The smoothed curve is then read back at the real timestamps, so
     `residual = mm − smoothed` is only evaluated at measured samples.
5. **Metrics:**
   - `smoothness_mm` is the residual RMS over the descent.
   - `wobble_ratio` is the residual RMS where `smoothed ≤ min(smoothed) + FINAL_ZONE_MM`,
     divided by the residual RMS before that zone.
   - An attempt needs at least `MIN_ZONE_SAMPLES` in each zone and a non-zero residual before
     the zone.
6. The result averages both metrics over the valid attempts. If there are none, it raises
   `no_descent_detected`.

| Constant | Value | Units | Meaning |
|---|---|---|---|
| `START_DROP_MM` | 20.0 | mm | Drop below the highest point that starts a descent |
| `END_MM` | 40.0 | mm | Height that ends a descent |
| `STALL_S` | 0.5 | s | Time without a new low that ends a descent |
| `DECREASE_EPS_MM` | 2.0 | mm | How far below the running low a reading must be to count as decreasing (about 2× ToF noise) |
| `SG_WINDOW_S` | 0.3 | s | Savitzky–Golay window length |
| `SG_POLYORDER` | 2 | — | Savitzky–Golay polynomial order |
| `SG_MIN_WINDOW` | 5 | samples | Smallest SG window, and the shortest descent accepted |
| `FINAL_ZONE_MM` | 50.0 | mm | Height of the end zone above the lowest smoothed point |
| `MIN_ZONE_SAMPLES` | 2 | samples | Least samples in each wobble zone |
| `TOF_MAX_MM` | 1300.0 | mm | Readings above this mean out of view |

Reach accepts readings from 1 mm up. Posture's 20 mm lower bound doesn't apply, because a reach
ends close to the sensor.

**Synthetic behavior** (300 → 30 mm min-jerk over 2.5 s, 1 mm noise, 300 seeds):

| Case | Wobble ratio | Smoothness |
|---|---|---|
| 40 Hz, smooth | mean 1.01, p95 1.42, p99 1.62 | 0.73–1.03 mm |
| 50 Hz, smooth | 0.63–1.32 (30 seeds) | 0.82–1.08 mm |
| 40 Hz, 6 mm 8 Hz end wobble | ≥ 3.4 | 2.3–2.9 mm |
| 50 Hz, integer mm, 20% stale repeats, 5% dropped | within the smooth range | within 35% of clean |

At 40 Hz the end zone holds only about 18 samples, so one smooth attempt can occasionally read
above 1.5. Averaging three attempts narrows that.

## Finger taps (`tap.py`)

`analyze_taps(frames)` takes MediaPipe frames: `t` in seconds, plus landmarks 0, 4, 8 and 9.

1. **Signal** (`tap_signal`): `|p4 − p8| / |p0 − p9|` (thumb-index gap over the wrist-to-middle-MCP
   distance). Frames are dropped when:
   - they have no hand;
   - they have fewer than 4 landmarks or non-finite values;
   - the hand size is ≤ `MIN_HAND_SIZE`.

   Frames are sorted by time, and only the first frame at a repeated timestamp is kept. The
   frame rate is never assumed: browser timestamps are uneven.
2. **Taps:** `find_peaks(signal, prominence=TAP_PROMINENCE)`. With fewer than `MIN_TAPS`, it
   raises `no_taps_detected`. That includes no frames at all, or no hand in any frame.
3. **Tap times:** each peak is refined with a parabola through it and its two neighbors, on
   the real timestamps. With plain frame times, 30 fps quantization alone gives a rhythm CV of
   0.06–0.09, as large as real rhythm variability. Refined, it is about 0.01.
4. **Metrics:**
   - `taps_per_sec = (n − 1) / (t_last − t_first)`, using refined times.
   - Each tap's amplitude is the peak minus the lowest signal since the previous peak (since
     the first frame, for the first tap). `amplitude` is the mean.
   - `decrement = (mean amplitude of the taps within EDGE_WINDOW_S of the last tap − same for
     the first tap) / first`. Anchoring on the taps, not on the recording edges, keeps both
     windows non-empty when the user starts late or stops early. It is 0.0 if the first mean
     is ≤ 0.
   - `rhythm_cv` is std ÷ mean of the inter-tap intervals (population std).

| Constant | Value | Units | Meaning |
|---|---|---|---|
| `TAP_PROMINENCE` | 0.15 | signal units | Smallest peak prominence that counts as a tap |
| `EDGE_WINDOW_S` | 3.0 | s | First and last window for the decrement |
| `MIN_TAPS` | 3 | taps | Fewer raises `no_taps_detected` |
| `MIN_HAND_SIZE` | 1e-6 | image units | A smaller `|p0 − p9|` means a degenerate frame |
| `LANDMARK_COUNT` | 4 | — | Landmarks expected per frame |

**Synthetic behavior** (4 Hz, 10 s, 30 fps, amplitude 1.0 → 0.7, 100 seeds):

| Case | Rate | Decrement | CV |
|---|---|---|---|
| Clean | 3.998–4.002 | −0.315 to −0.288 | 0.006–0.011 |
| Every 7th frame dropped, ±20% frame jitter | 3.998–4.002 | −0.339 to −0.263 | 0.007–0.012 |

## Baseline (`baseline.py`)

`compare(value, history, min_n=BASELINE_MIN_N)` returns `100 · (value − mean) / |mean|`, the
percent difference from the mean of the user's history. Non-finite history entries are
ignored. It returns `None` ("building your baseline") when:

- there are fewer than `min_n` finite entries;
- the mean is 0;
- the value is not finite.

| Constant | Value | Units | Meaning |
|---|---|---|---|
| `BASELINE_MIN_N` | 3 | entries | History needed before a percentage is shown |

## How to tune (against a real still hand)

1. Record at least 5 rest tests of a still hand, using the rest protocol: the sensor lies flat in
   an open palm (not gripped) with the forearm resting. Record 5 more with a deliberate tremor of
   known frequency (e.g. shaking to a 300 BPM metronome, which is 5 Hz).
2. For each one, log `strength_ms2` and the ratio `max(psd[band]) / median(psd[band])`.
3. Set `RMS_MIN_MS2` about 1.5× above the largest still-hand `strength_ms2` on the **shortest**
   live window. Real hands carry physiological tremor (8–12 Hz), far above the simulator's noise.
4. Set `PEAK_TO_MEDIAN_MIN` above the largest still-hand ratio on the **shortest** window you
   display (the live spectrum's first seconds) and below the smallest tremor ratio.
5. Keep `SCORE_FLOOR_MS2` close to the still-hand RMS so a still hand scores near 0. Changing a
   score constant rescales every stored score, so make that change before collecting history.
6. If you change `WELCH_WINDOW_S`, re-check the ±0.25 Hz tests. Shorter windows give coarser
   bins and noisier peaks. `MIN_RUN_S` should stay at least one Welch window long.
7. For posture, widen `BAND_HALF_WIDTH_MM` if real users drift out of band often (watch
   `valid_seconds` in failed tests). Raise `TOF_MATCH_MAX_S` only if the ToF rate drops below
   about 10 Hz.
