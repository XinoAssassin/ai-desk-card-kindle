#include "sleep_card.h"
#include "frame_receiver.h"

#include <LittleFS.h>

namespace {
constexpr const char* PATH = "/sleep_card.bin";
constexpr int SC_FRAME_W = 540;
constexpr int SC_FRAME_H = 960;
constexpr size_t EXPECTED_BYTES = (size_t)SC_FRAME_W * SC_FRAME_H / 2;
}

bool sleepCardAvailable() {
    if (!LittleFS.begin(false)) {
        Serial.println("[sleep_card] LittleFS mount failed");
        return false;
    }
    if (!LittleFS.exists(PATH)) {
        Serial.println("[sleep_card] /sleep_card.bin missing — "
                       "run build_sleep_card.py + uploadfs");
        return false;
    }
    File f = LittleFS.open(PATH, "r");
    if (!f) return false;
    size_t sz = f.size();
    f.close();
    if (sz != EXPECTED_BYTES) {
        Serial.printf("[sleep_card] size %u != expected %u\n",
                      (unsigned)sz, (unsigned)EXPECTED_BYTES);
        return false;
    }
    return true;
}

bool sleepCardDisplay() {
    if (!sleepCardAvailable()) return false;
    if (!frameAcquireBuffer()) {
        Serial.println("[sleep_card] frame buffer busy");
        return false;
    }
    File f = LittleFS.open(PATH, "r");
    if (!f) { frameReleaseBuffer(); return false; }
    uint8_t* buf = frameBuffer();
    size_t got = f.read(buf, EXPECTED_BYTES);
    f.close();
    if (got != EXPECTED_BYTES) {
        Serial.printf("[sleep_card] short read %u\n", (unsigned)got);
        frameReleaseBuffer();
        return false;
    }
    Serial.println("[sleep_card] painting business card from LittleFS");
    frameDisplay(0, 0, SC_FRAME_W, SC_FRAME_H);
    frameReleaseBuffer();
    return true;
}
