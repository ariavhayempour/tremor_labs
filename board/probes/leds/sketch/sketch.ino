#include <Arduino_LED_Matrix.h>

const unsigned long STEP_US = 1000000;
const uint8_t ROWS = 8, COLS = 13, ON = 7;
Arduino_LED_Matrix matrix;
uint8_t frame[ROWS * COLS];
unsigned long next_us = 0;
int step = 0;

// 3x5 glyphs, one row per byte, bit 2 = left column.
const uint8_t DIGITS[10][5] = {
  {7, 5, 5, 5, 7}, {2, 6, 2, 2, 7}, {7, 1, 7, 4, 7}, {7, 1, 7, 1, 7}, {5, 5, 7, 1, 1},
  {7, 4, 7, 1, 7}, {7, 4, 7, 5, 7}, {7, 1, 1, 1, 1}, {7, 5, 7, 5, 7}, {7, 5, 7, 1, 7},
};
const uint8_t CHECK[ROWS][COLS] = {
  {0,0,0,0,0,0,0,0,0,0,0,0,0}, {0,0,0,0,0,0,0,0,0,0,1,0,0}, {0,0,0,0,0,0,0,0,0,1,0,0,0},
  {0,0,0,0,0,0,0,0,1,0,0,0,0}, {0,0,0,1,0,0,0,1,0,0,0,0,0}, {0,0,0,0,1,0,1,0,0,0,0,0,0},
  {0,0,0,0,0,1,0,0,0,0,0,0,0}, {0,0,0,0,0,0,0,0,0,0,0,0,0},
};

void draw_digit(int d) {
  memset(frame, 0, sizeof(frame));
  for (int r = 0; r < 5; r++)
    for (int c = 0; c < 3; c++)
      if (DIGITS[d][r] & (4 >> c)) frame[(r + 1) * COLS + 5 + c] = ON;
  matrix.draw(frame);
}

void draw_check() {
  for (int r = 0; r < ROWS; r++)
    for (int c = 0; c < COLS; c++) frame[r * COLS + c] = CHECK[r][c] ? ON : 0;
  matrix.draw(frame);
}

void set_rgb(int r, int g, int b) {
  digitalWrite(LED3_R, r);
  digitalWrite(LED3_G, g);
  digitalWrite(LED3_B, b);
}

void show(int s) {
  switch (s) {
    case 0: draw_digit(3); set_rgb(HIGH, LOW, LOW); break;
    case 1: draw_digit(2); set_rgb(LOW, HIGH, LOW); break;
    case 2: draw_digit(1); set_rgb(LOW, LOW, HIGH); break;
    default: draw_check(); set_rgb(LOW, LOW, LOW); break;
  }
}

void setup() {
  pinMode(LED3_R, OUTPUT);
  pinMode(LED3_G, OUTPUT);
  pinMode(LED3_B, OUTPUT);
  matrix.begin();
  matrix.setGrayscaleBits(3);
  matrix.clear();
  show(step);
  next_us = micros() + STEP_US;
}

void loop() {
  if ((long)(micros() - next_us) >= 0) {
    next_us += STEP_US;
    step = (step + 1) % 4;
    show(step);
  }
}
