#include "feedback_led.h"
#include <M5Unified.h>

// M5Unified has a built-in LED API via M5.Power.setLed() on devices
// with simple LEDs, but Paper Color's WS2812 chain needs raw bit-bang
// or a NeoPixel lib. For minimal deps + reliable timing we use the
// ESP32 RMT peripheral directly via Arduino's analogWrite-equivalent.
// Until we wire up RMT, ledColor() is a no-op and the helpers below
// just log to Serial — visual feedback comes from the panel and audio
// alone for v1.
//
// TODO Phase 4.5: add proper WS2812 driving (esp32-hal-rmt-based).

void ledInit() {
    Serial.println("[led] init (stub — RMT/WS2812 driver TBD)");
}

void ledColor(uint8_t r, uint8_t g, uint8_t b) {
    (void)r; (void)g; (void)b;
}

void ledOff() {}

void ledBlinkAck() {
    Serial.println("[led] ack-blink (stub)");
}

void ledPulseInbound() {
    Serial.println("[led] inbound-pulse (stub)");
}
