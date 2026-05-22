// Audio helpers — Paper Color has an ES8311 codec + 1 W speaker. We use
// M5Unified's M5.Speaker abstraction (PWM-style synthesis of sine tones).
// Three presets cover the common notification cases:
//   - chime:  three ascending notes, ~600 ms total. Soft "look at card".
//   - urgent: three short fast beeps, ~400 ms. Overdue / now / fired.
//   - alert:  single sharp tone ~150 ms. Tap-ack / generic ping.

#pragma once
#include <Arduino.h>

void audioInit();           // sets up M5.Speaker, idempotent
void audioBeepChime();
void audioBeepUrgent();
void audioBeepAlert();
// Raw tone for /beep custom requests.
void audioTone(uint16_t freq_hz, uint16_t duration_ms);
