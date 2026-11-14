#include "Arduino_RouterBridge.h"
#include <vector>

const unsigned long SEND_US = 100000;   // 10 messages per second
const int SENDS_PER_SIZE = 30;          // 3 s per size
const int SIZES[] = {10, 35, 70, 140, 280, 560};
const int N_SIZES = sizeof(SIZES) / sizeof(SIZES[0]);

int size_idx = 0, sent = 0;
unsigned long next_us = 0;
std::vector<int> payload;

void start_size() {
  payload.assign(SIZES[size_idx], 0);
  for (int i = 0; i < SIZES[size_idx]; i++) payload[i] = 100000 + i;
  sent = 0;
  Bridge.notify("phase", SIZES[size_idx]);
}

void setup() {
  Bridge.begin();
  start_size();
  next_us = micros() + SEND_US;
}

void loop() {
  if ((long)(micros() - next_us) >= 0) {
    next_us += SEND_US;
    if (sent == SENDS_PER_SIZE) {
      size_idx = (size_idx + 1) % N_SIZES;
      start_size();
    }
    Bridge.notify("vec", payload);
    sent++;
  }
}
