#include "feedback_led.h"
#include <Adafruit_NeoPixel.h>

// Paper Color has 2 WS2812-class RGB LEDs daisy-chained on G21.
// Adafruit_NeoPixel handles the strict 800 kHz timing via the RMT
// peripheral on ESP32-S3.

namespace {
constexpr int LED_PIN   = 21;
constexpr int LED_COUNT = 2;
Adafruit_NeoPixel g_strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

void writeAll(uint8_t r, uint8_t g, uint8_t b) {
    for (int i = 0; i < LED_COUNT; ++i)
        g_strip.setPixelColor(i, g_strip.Color(r, g, b));
    g_strip.show();
}
}   // namespace

void ledInit() {
    g_strip.begin();
    g_strip.setBrightness(80);   // 0-255; keep moderate for desk use
    g_strip.clear();
    g_strip.show();
    Serial.println("[led] NeoPixel initialised (2 LEDs on G21)");
}

void ledColor(uint8_t r, uint8_t g, uint8_t b) { writeAll(r, g, b); }
void ledOff()                                  { writeAll(0, 0, 0); }

void ledBlinkAck() {
    // Short white flash — used as tap-ack for button presses.
    writeAll(255, 255, 255);
    delay(60);
    writeAll(0, 0, 0);
}

void ledPulseInbound() {
    // Single green pulse — called when /frame arrives. Visual nudge that
    // bytes are flowing before the slow Spectra 6 refresh kicks in.
    writeAll(0, 180, 60);
    delay(40);
    writeAll(0, 80, 30);
    delay(40);
    writeAll(0, 0, 0);
}
