#include <Arduino_Modulino.h>
#include <Arduino_RouterBridge.h>

const unsigned long REPORT_US = 1000000;
ModulinoMovement movement;
ModulinoDistance distance;
bool movement_ok = false;
bool distance_ok = false;
unsigned long next_report_us = 0;
int imu_count = 0, tof_avail = 0, tof_new = 0, invalid_polls = 0, loops = 0;
float last_mm = NAN;

void setup() {
  Bridge.begin();
  Modulino.begin(Wire1);
  movement_ok = movement.begin();
  distance_ok = distance.begin();
  next_report_us = micros() + REPORT_US;
}

void loop() {
  loops++;
  if (movement_ok && movement.available()) {
    movement.update();
    imu_count++;
  }
  if (distance_ok) {
    if (distance.available()) {
      tof_avail++;
      float mm = distance.get();
      // available() repeats the last result, so only a changed value counts as a new reading.
      if (mm != last_mm) {
        tof_new++;
        last_mm = mm;
      }
    } else {
      invalid_polls++;
    }
  }
  if ((long)(micros() - next_report_us) >= 0) {
    next_report_us += REPORT_US;
    Bridge.notify("rates", imu_count, tof_avail, tof_new, invalid_polls, loops, (int)movement_ok, (int)distance_ok);
    imu_count = tof_avail = tof_new = invalid_polls = loops = 0;
  }
}
