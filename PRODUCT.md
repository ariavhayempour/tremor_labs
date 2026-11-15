# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Patient** already diagnosed with a tremor condition (e.g. Parkinson's disease, essential tremor), at a table at home, running 2–6 short checks a day, often timed around medication.
- **Caregiver** who reads the trends dashboard to see when tremor changes.
- **Neurologist** who reads the printable report between visits.
- Trend views serve patient/caregiver and neurologist equally: a plain-language summary plus a clinical level of detail on the same screen.

## Product Purpose

Tremor Lab replaces a subjective paper symptom diary with a guided 2-minute movement check (rest, posture, reach, tap). Each check is logged next to medication times, so people can see when tremor changes across the day and over weeks. Success: a patient, caregiver or neurologist can tell how tremor relates to dose timing without reading raw numbers.

## Positioning

Objective, sensor-measured checks (a 6-axis IMU, a time-of-flight distance sensor and the laptop camera) on a local Arduino UNO Q, compared only against the user's own baseline, with all data kept on the user's own machine.

## Operating Context

- Board at the table edge with an LED matrix facing the user; the patient holds the movement sensor; the laptop runs the browser UI at `http://localhost`.
- A check: medication check-in, rest (30 s), posture (30 s in the height band), reach (3 attempts), tap (10 s per hand), then results against baseline.
- Trends span a window of days (default 14) and are also exported as a one-page printable doctor report.

## Capabilities and Constraints

- A tracking tool, **not a medical device**. It never labels a condition, never says "diagnosis" or "you have", and never advises medication changes. User-facing copy lives in `frontend/src/copy.ts`.
- Available trend data (see `docs/contracts.md`): rest-tremor strength binned by hours since dose (0–6 h, 0.5 h bins, with counts) and a "tremor returns after X h" value; daily mean rest strength with check counts; per-test first-week vs last-3-days profile; per-check results (rest/posture strength score 0–100 and peak Hz, reach smoothness in mm and end-of-reach wobble ratio, taps/s, tap amplitude decrement, rhythm variability) per hand; dose times.
- No lifestyle factors (caffeine, sleep, stress, alcohol) are collected or shown.
- Baselines appear only after 3 or more checks; before that the UI says it is building the baseline. Every insight shows its sample count.
- Everything runs locally: no CDNs at runtime, no cloud services, no external calls with user data.
- Stack: Vite + React + TypeScript, Tailwind v4 + shadcn/ui, Recharts for dashboard charts, canvas for live streams.

## Brand Commitments

- Name: Tremor Lab. Voice: plain, friendly, non-diagnostic.
- Footer on dashboard and report: "Tremor Lab is a tracking tool, not a medical device. Discuss results with your doctor."
- The user asked for a fresh, clean, professional feel.

## Evidence on Hand

- Deterministic 14-day demo data from `scripts/seed.py` (doses at 08:00, 13:00, 18:00; 3–4 checks a day; peak frequency 4.5–5.5 Hz). It is synthetic and must be labelled as such wherever it could be mistaken for real data.
- No testimonials, clinical validation claims or customer data exist; none may be invented.

## Product Principles

1. Show patterns against dose timing first; individual numbers second.
2. Compare a person only to their own baseline, never to a population norm.
3. Every chart states its sample count and units; thin data says so.
4. Describe, never interpret medically.

## Accessibility & Inclusion

Primary users may have tremor and reduced fine motor control: generous hit targets, no precision hover-only interactions, and no information conveyed by colour alone.
