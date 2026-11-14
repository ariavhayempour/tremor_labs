-- Tremor Lab schema. Timestamps are ISO-8601 UTC strings; booleans are 0/1 integers.

CREATE TABLE IF NOT EXISTS doses (
    id        INTEGER PRIMARY KEY,
    taken_at  TEXT NOT NULL,
    label     TEXT
);
CREATE INDEX IF NOT EXISTS idx_doses_taken_at ON doses(taken_at);

CREATE TABLE IF NOT EXISTS checks (
    id                  INTEGER PRIMARY KEY,
    created_at          TEXT NOT NULL,
    minutes_since_dose  REAL,
    caffeine            INTEGER CHECK (caffeine IN (0, 1)),
    sleep_quality       INTEGER CHECK (sleep_quality BETWEEN 1 AND 5),
    stress              INTEGER CHECK (stress BETWEEN 1 AND 5),
    alcohol             INTEGER CHECK (alcohol IN (0, 1)),
    notes               TEXT,
    dose_id             INTEGER REFERENCES doses(id)
);
CREATE INDEX IF NOT EXISTS idx_checks_created_at ON checks(created_at);

CREATE TABLE IF NOT EXISTS tests (
    id            INTEGER PRIMARY KEY,
    check_id      INTEGER NOT NULL REFERENCES checks(id),
    type          TEXT NOT NULL CHECK (type IN ('rest', 'posture', 'reach', 'tap')),
    hand          TEXT NOT NULL CHECK (hand IN ('left', 'right')),
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    status        TEXT NOT NULL CHECK (status IN ('recording', 'analyzing', 'done', 'failed')),
    fail_reason   TEXT,
    markers_json  TEXT
);
CREATE INDEX IF NOT EXISTS idx_tests_check_id ON tests(check_id);

CREATE TABLE IF NOT EXISTS results (
    test_id              INTEGER PRIMARY KEY REFERENCES tests(id),
    peak_hz              REAL,
    strength_ms2         REAL,
    strength_score       REAL,
    tremor_detected      INTEGER CHECK (tremor_detected IN (0, 1)),
    smoothness           REAL,
    wobble_ratio         REAL,
    taps_per_sec         REAL,
    tap_amplitude        REAL,
    amplitude_decrement  REAL,
    rhythm_cv            REAL,
    valid_seconds        REAL,
    details_json         TEXT
);

CREATE TABLE IF NOT EXISTS raw_samples (
    id            INTEGER PRIMARY KEY,
    test_id       INTEGER NOT NULL REFERENCES tests(id),
    sensor        TEXT NOT NULL CHECK (sensor IN ('imu', 'tof')),
    payload_json  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_raw_samples_test_id ON raw_samples(test_id);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
