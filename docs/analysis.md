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

The score is logarithmic because tremor amplitude spans orders of magnitude. 0.005 m/s² maps to
0 and 2.0 m/s² maps to 100. Each doubling of the RMS adds about 11.6 points. Examples:
0.02 → 23, 0.1 → 50, 0.2 → 62, 0.5 → 77.

### Constants

| Constant | Value | Units | Meaning |
|---|---|---|---|
| `HP_CUTOFF_HZ` | 2.0 | Hz | High-pass cutoff (removes gravity, drift, voluntary movement) |
| `HP_ORDER` | 4 | — | Butterworth order (the zero-phase filter applies it twice) |
| `BAND_HZ` | (3.0, 12.0) | Hz | Tremor band for the peak search, the strength and the noise floor |
| `WELCH_WINDOW_S` | 4.0 | s | Welch segment length; gives 0.25 Hz resolution |
| `PEAK_TO_MEDIAN_MIN` | 6.0 | ratio | Peak PSD ÷ in-band median PSD needed to call a tremor |
| `RMS_MIN_MS2` | 0.02 | m/s² | Band RMS needed to call a tremor |
| `SCORE_FLOOR_MS2` | 0.005 | m/s² | RMS that maps to a score of 0 |
| `SCORE_CEIL_MS2` | 2.0 | m/s² | RMS that maps to a score of 100 |
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
| 5 Hz, amplitude 0.3 | ≫ 100 | 0.209 | yes |
| 5 Hz, amplitude 0.02 | — | 0.0205 | yes, barely |

On long windows the peak-ratio test separates a still hand from a tremor with a wide margin. A
4 s window has a single Welch segment and no averaging, so noise alone can pass the ratio test,
and only the RMS gate prevents a false detection. The simulator's noise sits at about 73% of
`RMS_MIN_MS2`.

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

## How to tune (against a real still hand)

1. Record at least 5 rest tests of a still hand, using the rest protocol: the sensor lies flat in
   an open palm (not gripped) with the forearm resting. Record 5 more with a deliberate tremor of
   known frequency (e.g. shaking to a 300 BPM metronome, which is 5 Hz).
2. For each one, log `strength_ms2` and the ratio `max(psd[band]) / median(psd[band])`.
3. Set `RMS_MIN_MS2` about 1.5× above the largest still-hand `strength_ms2`. Real accelerometer
   noise and small postural sway are usually higher than the simulator's.
4. Set `PEAK_TO_MEDIAN_MIN` above the largest still-hand ratio on the **shortest** window you
   display (the live spectrum's first seconds) and below the smallest tremor ratio.
5. Keep `SCORE_FLOOR_MS2` close to the still-hand RMS so a still hand scores near 0. Changing a
   score constant rescales every stored score, so make that change before collecting history.
6. If you change `WELCH_WINDOW_S`, re-check the ±0.25 Hz tests. Shorter windows give coarser
   bins and noisier peaks. `MIN_RUN_S` should stay at least one Welch window long.
7. For posture, widen `BAND_HALF_WIDTH_MM` if real users drift out of band often (watch
   `valid_seconds` in failed tests). Raise `TOF_MATCH_MAX_S` only if the ToF rate drops below
   about 10 Hz.
