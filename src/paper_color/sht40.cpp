#include "sht40.h"
#include <Wire.h>

namespace {
constexpr uint8_t  ADDR = 0x44;
constexpr int      PIN_SDA = 3;
constexpr int      PIN_SCL = 2;
constexpr uint32_t FREQ = 100000;   // SHT40 happy at 100 kHz

float    g_t = 0.0f;
float    g_h = 0.0f;
uint32_t g_last_ms = 0;
bool     g_present = false;
}

bool sht40Init() {
    Wire.begin(PIN_SDA, PIN_SCL, FREQ);
    Wire.beginTransmission(ADDR);
    g_present = (Wire.endTransmission() == 0);
    Serial.printf("[sht40] init: %s\n", g_present ? "found" : "missing");
    return g_present;
}

bool sht40Read() {
    if (!g_present) return false;
    // 0xFD = high-precision measurement, takes ~8.2 ms
    Wire.beginTransmission(ADDR);
    Wire.write(0xFD);
    if (Wire.endTransmission() != 0) return false;
    delay(10);
    if (Wire.requestFrom(ADDR, (uint8_t)6) != 6) return false;
    uint8_t b[6];
    for (int i = 0; i < 6; ++i) b[i] = Wire.read();
    // bytes: T_msb T_lsb T_crc H_msb H_lsb H_crc — we skip CRC check.
    uint16_t rt = ((uint16_t)b[0] << 8) | b[1];
    uint16_t rh = ((uint16_t)b[3] << 8) | b[4];
    g_t = -45.0f + 175.0f * ((float)rt / 65535.0f);
    g_h = -6.0f  + 125.0f * ((float)rh / 65535.0f);
    if (g_h < 0)   g_h = 0;
    if (g_h > 100) g_h = 100;
    g_last_ms = millis();
    return true;
}

float sht40LastTempC()  { return g_t; }
float sht40LastHumidPct() { return g_h; }
uint32_t sht40LastReadMs() { return g_last_ms; }
