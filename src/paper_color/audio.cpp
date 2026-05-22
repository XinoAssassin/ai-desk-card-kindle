#include "audio.h"
#include <M5Unified.h>

namespace {
bool g_inited = false;

void ensureInit() {
    if (g_inited) return;
    // M5Unified picks the right codec/speaker driver from board detection.
    // Bump volume to a usable level (default is low; max is 255).
    M5.Speaker.begin();
    M5.Speaker.setVolume(180);
    g_inited = true;
    Serial.println("[audio] M5.Speaker initialised");
}

// M5.Speaker.tone() is non-blocking — schedules the tone, returns
// immediately. We sleep between tones so a "pattern" sounds like notes
// rather than overlapping.
void playSequence(const uint16_t* freqs, const uint16_t* durs, size_t n,
                  uint16_t gap_ms = 30) {
    ensureInit();
    for (size_t i = 0; i < n; ++i) {
        M5.Speaker.tone(freqs[i], durs[i]);
        delay(durs[i] + gap_ms);
    }
}
}   // namespace

void audioInit() { ensureInit(); }

void audioBeepChime() {
    // C5 → E5 → G5 — classic soft chime. ~600 ms.
    static const uint16_t f[] = {523, 659, 784};
    static const uint16_t d[] = {180, 180, 220};
    playSequence(f, d, 3);
}

void audioBeepUrgent() {
    // Three rapid 880 Hz blips with short gaps. ~400 ms total.
    static const uint16_t f[] = {880, 880, 880};
    static const uint16_t d[] = {90, 90, 110};
    playSequence(f, d, 3, 50);
}

void audioBeepAlert() {
    // Single short high tone.
    static const uint16_t f[] = {1320};
    static const uint16_t d[] = {150};
    playSequence(f, d, 1);
}

void audioTone(uint16_t freq_hz, uint16_t duration_ms) {
    ensureInit();
    if (freq_hz < 50 || freq_hz > 12000) return;
    if (duration_ms == 0) duration_ms = 100;
    if (duration_ms > 3000) duration_ms = 3000;
    M5.Speaker.tone(freq_hz, duration_ms);
    delay(duration_ms);
}
