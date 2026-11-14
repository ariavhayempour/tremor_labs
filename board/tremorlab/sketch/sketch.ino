#include <Arduino_LED_Matrix.h>
#include <Arduino_Modulino.h>
#include <Arduino_RouterBridge.h>
#include <vector>

#include "font.h"

// Timing (all scheduled with micros(); never delay()).
const unsigned long IMU_PERIOD_US = 10000;     // 100 Hz
const unsigned long TOF_PERIOD_US = 20000;     // matches the sensor's 20 ms timing budget
// notify() blocks while the serial link sends, so batches stay small enough to fit between IMU samples.
const size_t IMU_SAMPLES_PER_NOTIFY = 1;
const size_t TOF_SAMPLES_PER_NOTIFY = 1;
const unsigned long STATUS_PERIOD_US = 1000000;
const unsigned long IDLE_STEP_US = 80000;
const long TOF_GUARD_US = 4000;  // skip a ToF poll if the next IMU sample is closer than one poll takes

// LED matrix and RGB LED3 (active-low: LOW = on).
const uint8_t ROWS = 8, COLS = 13, LEVEL_ON = 7;

ModulinoMovement movement;
ModulinoDistance distance;
Arduino_LED_Matrix matrix;

bool movement_ok = false, distance_ok = false, recording = false, idle_on = false;
unsigned long next_imu_us, next_tof_us, next_status_us, next_idle_us;
int imu_count = 0, tof_count = 0, nan_count = 0, idle_phase = 0;
std::vector<int> imu_buf, tof_buf;
uint8_t frame[ROWS * COLS];

bool due(unsigned long t) { return (long)(micros() - t) >= 0; }

// Round to nearest; libm rounding functions are not linked on this core.
int round_int(float x) { return (int)(x >= 0.0f ? x + 0.5f : x - 0.5f); }

void set_rgb(bool r, bool g, bool b) {
  digitalWrite(LED3_R, r ? LOW : HIGH);
  digitalWrite(LED3_G, g ? LOW : HIGH);
  digitalWrite(LED3_B, b ? LOW : HIGH);
}

void show_state_color() {
  if (!movement_ok || !distance_ok) set_rgb(true, false, false);
  else if (recording) set_rgb(false, false, true);
  else set_rgb(false, true, false);
}

void draw_icon(const uint8_t icon[ROWS][COLS]) {
  for (int r = 0; r < ROWS; r++)
    for (int c = 0; c < COLS; c++) frame[r * COLS + c] = icon[r][c] ? LEVEL_ON : 0;
  matrix.draw(frame);
}

void put_digit(int d, int col) {
  for (int r = 0; r < 5; r++)
    for (int c = 0; c < 3; c++)
      if (DIGITS[d][r] & (4 >> c)) frame[(r + 1) * COLS + col + c] = LEVEL_ON;
}

void draw_number(int n) {
  memset(frame, 0, sizeof(frame));
  n = constrain(n, 0, 99);
  if (n < 10) {
    put_digit(n, 5);
  } else {
    put_digit(n / 10, 3);
    put_digit(n % 10, 7);
  }
  matrix.draw(frame);
}

void draw_idle_step() {
  // Breathing: a centered diamond whose brightness ramps 0..7..0.
  int level = idle_phase < 8 ? idle_phase : 15 - idle_phase;
  for (int r = 0; r < ROWS; r++)
    for (int c = 0; c < COLS; c++) frame[r * COLS + c] = (abs(r * 2 - 7) + abs(c * 2 - 12) <= 9) ? level : 0;
  matrix.draw(frame);
  idle_phase = (idle_phase + 1) % 16;
}

enum LedCmd { LED_NONE, LED_COUNTDOWN, LED_HOLD, LED_CHECK, LED_IDLE, LED_CLEAR, LED_RECORDING };
volatile int pending_cmd = LED_NONE;
volatile int pending_value = 0;

// Runs on the Bridge thread: only records the command; loop() applies it.
void on_led(String cmd, int value) {
  int code = cmd == "countdown" ? LED_COUNTDOWN : cmd == "hold" ? LED_HOLD : cmd == "check" ? LED_CHECK
           : cmd == "idle" ? LED_IDLE : cmd == "clear" ? LED_CLEAR : cmd == "recording" ? LED_RECORDING : LED_NONE;
  pending_value = value;
  pending_cmd = code;
}

void apply_led(int code, int value) {
  if (code != LED_RECORDING) idle_on = false;
  switch (code) {
    case LED_COUNTDOWN: draw_number(value); break;
    case LED_HOLD: draw_icon(HOLD_ICON); break;
    case LED_CHECK: draw_icon(CHECK_ICON); break;
    case LED_IDLE: idle_on = true; idle_phase = 0; next_idle_us = micros(); break;
    case LED_CLEAR: matrix.clear(); break;
    case LED_RECORDING: recording = value != 0; show_state_color(); break;
    default: break;
  }
}

void sample_imu(unsigned long t_us) {
  movement.update();
  imu_buf.push_back((int)t_us);
  imu_buf.push_back(round_int(movement.getX() * 1000.0f));
  imu_buf.push_back(round_int(movement.getY() * 1000.0f));
  imu_buf.push_back(round_int(movement.getZ() * 1000.0f));
  imu_buf.push_back(round_int(movement.getRoll() * 1000.0f));
  imu_buf.push_back(round_int(movement.getPitch() * 1000.0f));
  imu_buf.push_back(round_int(movement.getYaw() * 1000.0f));
  imu_count++;
}

void sample_tof(unsigned long t_us) {
  // available() re-reports the last valid result, so readings are sampled at a fixed rate instead.
  if (distance.available()) {
    tof_buf.push_back((int)t_us);
    tof_buf.push_back(round_int(distance.get()));
    tof_count++;
  } else {
    nan_count++;
  }
}

// 0 ok, 1 movement_missing, 2 distance_missing, 3 both_missing (the relay maps these to text).
int status_code() { return (movement_ok ? 0 : 1) + (distance_ok ? 0 : 2); }

void setup() {
  pinMode(LED3_R, OUTPUT);
  pinMode(LED3_G, OUTPUT);
  pinMode(LED3_B, OUTPUT);
  matrix.begin();
  matrix.setGrayscaleBits(3);
  matrix.clear();

  Bridge.begin();
  Modulino.begin(Wire1);
  movement_ok = movement.begin();
  distance_ok = distance.begin();
  show_state_color();
  Bridge.provide("led", on_led);

  unsigned long now = micros();
  next_imu_us = now + IMU_PERIOD_US;
  next_tof_us = now + TOF_PERIOD_US;
  next_status_us = now + STATUS_PERIOD_US;
  next_idle_us = now;
}

void loop() {
  if (movement_ok && due(next_imu_us)) {
    unsigned long t = micros();
    next_imu_us += IMU_PERIOD_US;
    // After a long stall, resync instead of bursting to catch up.
    if (due(next_imu_us)) next_imu_us = t + IMU_PERIOD_US;
    sample_imu(t);
  }
  bool imu_clear = !movement_ok || (long)(next_imu_us - micros()) > TOF_GUARD_US;
  if (distance_ok && due(next_tof_us) && imu_clear) {
    unsigned long t = micros();
    next_tof_us += TOF_PERIOD_US;
    if (due(next_tof_us)) next_tof_us = t + TOF_PERIOD_US;
    sample_tof(t);
  }
  if (imu_buf.size() >= 7 * IMU_SAMPLES_PER_NOTIFY) {
    Bridge.notify("imu", imu_buf);
    imu_buf.clear();
  }
  if (tof_buf.size() >= 2 * TOF_SAMPLES_PER_NOTIFY) {
    Bridge.notify("tof", tof_buf);
    tof_buf.clear();
  }
  if (due(next_status_us)) {
    next_status_us += STATUS_PERIOD_US;
    Bridge.notify("status", status_code(), imu_count, tof_count, nan_count);
    imu_count = tof_count = nan_count = 0;
  }
  if (pending_cmd != LED_NONE) {
    int code = pending_cmd, value = pending_value;
    pending_cmd = LED_NONE;
    apply_led(code, value);
  }
  if (idle_on && due(next_idle_us)) {
    next_idle_us += IDLE_STEP_US;
    draw_idle_step();
  }
}
