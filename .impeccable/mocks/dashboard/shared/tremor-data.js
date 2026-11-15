// Synthetic 14-day demo dataset for the dashboard mockups. Mirrors backend/tremorlab/seeding.py.
(function () {
  let s = 42;
  const rand = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  const gauss = () => { const u = rand() || 1e-9, v = rand(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
  const uni = (a, b) => a + (b - a) * rand();
  const r = (x, n = 2) => Math.round(x * 10 ** n) / 10 ** n;

  const FLOOR = 0.06, RANGE = 0.34, MID = 3.0, WIDTH = 0.5, ONSET = 1.0, NOISE = 0.12;
  const base = (h) => FLOOR + RANGE / (1 + Math.exp(-(h - MID) / WIDTH));
  const score = (ms2) => (ms2 <= 0.05 ? 0 : Math.min(100, 50 * Math.log10(ms2 / 0.05)));

  const DAYS = 14;
  const end = new Date('2026-11-14T00:00:00');
  const DOSE_TIMES = ['08:00', '13:00', '18:00'];
  const mins = (hhmm) => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m; };

  const days = [], checks = [], doses = [];
  let id = 1;
  for (let d = DAYS - 1; d >= 0; d--) {
    const day = new Date(end); day.setDate(end.getDate() - d);
    const iso = day.toISOString().slice(0, 10);
    const doseMin = DOSE_TIMES.map((t) => mins(t) + uni(-10, 10));
    doseMin.forEach((m, i) => doses.push({ date: iso, minute: r(m, 0), slot: ['Morning', 'Midday', 'Evening'][i] }));
    const n = rand() < 0.5 ? 3 : 4;
    let times;
    do { times = Array.from({ length: n }, () => uni(mins('07:30'), mins('21:30'))).sort((a, b) => a - b); }
    while (!times.every((t, i) => i === 0 || t - times[i - 1] >= 30));
    const dayChecks = [];
    for (const t of times) {
      const prior = doseMin.filter((m) => m <= t);
      const last = prior.length ? prior[prior.length - 1] : null;
      const h = last === null ? null : (t - last) / 60;
      const prevInterval = prior.length >= 2 ? (prior[prior.length - 1] - prior[prior.length - 2]) / 60 : null;
      let clean;
      if (h === null) clean = FLOOR + RANGE;
      else if (h >= ONSET) clean = base(h);
      else { const before = prevInterval === null ? FLOOR + RANGE : base(prevInterval); clean = before + (FLOOR - before) * (h / ONSET); }
      const rest = Math.max(0.03, clean * (1 + NOISE * gauss()));
      const rel = rest / 0.4;
      const posture = 0.7 * rest;
      const tapL = 4.2 - 0.8 * rel + 0.15 * gauss(), tapR = 4.4 - 0.8 * rel + 0.15 * gauss();
      const c = {
        id: id++, date: iso, minute: r(t, 0), hours_since_dose: h === null ? null : r(h, 2),
        dose_slot: last === null ? 'Before first dose' : ['Morning', 'Midday', 'Evening'][prior.length - 1],
        rest: { strength_ms2: r(rest, 3), score: r(score(rest), 1), peak_hz: rest >= 0.08 ? r(uni(4.5, 5.5), 2) : null },
        posture: { strength_ms2: r(posture, 3), score: r(score(posture), 1), peak_hz: posture >= 0.08 ? r(uni(4.5, 5.5), 2) : null, valid_s: r(uni(22, 30), 1) },
        reach: { smoothness_mm: r(2 + 4 * rel * (1 + 0.08 * gauss()), 2), wobble_ratio: r(1 + 1.5 * rel * (1 + 0.08 * gauss()), 2) },
        tap: {
          left: { taps_per_sec: r(tapL, 2), decrement: r(uni(-0.15, -0.05), 3), rhythm_cv: r(0.08 + 0.1 * rel, 3) },
          right: { taps_per_sec: r(tapR, 2), decrement: r(uni(-0.15, -0.05), 3), rhythm_cv: r(0.08 + 0.1 * rel, 3) },
        },
      };
      checks.push(c); dayChecks.push(c);
    }
    const mean = dayChecks.reduce((a, c) => a + c.rest.strength_ms2, 0) / dayChecks.length;
    days.push({ date: iso, mean_rest: r(mean, 3), count: dayChecks.length });
  }

  // dose-response bins: rest strength_ms2 by hours since dose, 0.5 h bins over 0-6 h (empty bins omitted)
  const bins = [];
  for (let b = 0; b < 12; b++) {
    const xs = checks.filter((c) => c.hours_since_dose !== null && c.hours_since_dose >= b * 0.5 && c.hours_since_dose < b * 0.5 + 0.5).map((c) => c.rest.strength_ms2);
    if (xs.length) bins.push({ start_h: b * 0.5, mean: r(xs.reduce((a, x) => a + x, 0) / xs.length, 3), count: xs.length });
  }
  const sorted = checks.map((c) => c.rest.strength_ms2).sort((a, b) => a - b);
  const median = sorted.length % 2 ? sorted[(sorted.length - 1) / 2] : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;
  const ret = bins.find((b) => b.start_h >= 1 && b.mean > median && b.count >= 3);

  const avg = (xs) => (xs.length ? xs.reduce((a, x) => a + x, 0) / xs.length : null);
  const firstWeek = checks.filter((c) => c.date < days[7].date), current = checks.filter((c) => c.date >= days[11].date);
  const metric = { rest: (c) => c.rest.score, posture: (c) => c.posture.score, reach: (c) => c.reach.smoothness_mm, tap: (c) => (c.tap.left.taps_per_sec + c.tap.right.taps_per_sec) / 2 };
  const profile = Object.entries(metric).map(([k, f]) => ({
    test_type: k, unit: k === 'reach' ? 'mm' : k === 'tap' ? 'taps/s' : 'score',
    first_week: r(avg(firstWeek.map(f)), 1), first_n: firstWeek.length, current: r(avg(current.map(f)), 1), current_n: current.length,
  }));

  let streak = 0; for (let i = days.length - 1; i >= 0 && days[i].count > 0; i--) streak++;

  window.TREMOR_DATA = {
    synthetic: true,
    period: { start: days[0].date, end: days[days.length - 1].date, days: DAYS },
    dose_times: DOSE_TIMES,
    summary: { checks_completed: checks.length, streak_days: streak, returns_after_h: ret ? ret.start_h : null, median_rest: median },
    daily: days, bins, profile, checks, doses,
    latest: checks[checks.length - 1],
  };
})();
