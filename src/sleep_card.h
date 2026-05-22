// Sleep-card from LittleFS.
//
// V1.1 firmware can paint the user's electronic business card without
// any daemon connection — the card is pre-rendered on the host (run
// `python3 tools/build_sleep_card.py` + `pio run -e card -t uploadfs`)
// and stored at /sleep_card.bin (259200 bytes raw 4bpp, matches
// frame_receiver's buffer format).
//
// Used by the idle-sleep timer (see main.cpp) and could be triggered
// manually via cmd:sleep_now_local if needed.

#pragma once
#include <Arduino.h>

// True if /sleep_card.bin exists on LittleFS with the right size.
bool sleepCardAvailable();

// Reads the file into the existing frame_receiver PSRAM buffer and
// displays it via frameDisplay(0,0,FRAME_W,FRAME_H). Returns true on
// successful display. Does NOT enter deep sleep — caller follows up
// with esp_deep_sleep_start() after the panel settles.
bool sleepCardDisplay();
