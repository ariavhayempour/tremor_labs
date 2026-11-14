#include "Arduino_RouterBridge.h"

const unsigned long TICK_US = 100000;  // 10 notifies per second
unsigned long counter = 0;
unsigned long next_us = 0;

void setup() {
  Bridge.begin();
  next_us = micros() + TICK_US;
}

void loop() {
  // Signed difference keeps the schedule correct across the 32-bit micros() rollover.
  if ((long)(micros() - next_us) >= 0) {
    next_us += TICK_US;
    counter++;
    Bridge.notify("tick", counter);
  }
}
