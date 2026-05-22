// Front RGB LED helpers. Paper Color has 2x WS2812-style LEDs on G21.
// We use them for:
//   - Boot ready: brief green double-blink
//   - Frame inbound: green pulse during /frame body read (~1-2 s)
//   - Button press ack: short white blink (panel is too slow for visual)
//   - Wi-Fi disconnect: red slow blink

#pragma once
#include <Arduino.h>

void ledInit();
void ledColor(uint8_t r, uint8_t g, uint8_t b);
void ledOff();
void ledBlinkAck();        // short white flash
void ledPulseInbound();    // green pulse start (call again to end)
