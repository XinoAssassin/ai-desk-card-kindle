// SHT40 temperature + humidity sensor (Sensirion, I2C addr 0x44).
// On Paper Color: SDA=G3, SCL=G2. Init Wire bus, then call read() to
// fetch one measurement. Caches last reading + last_read_ms for the
// /status endpoint.

#pragma once
#include <Arduino.h>

bool  sht40Init();      // probe + setup; returns true if present
bool  sht40Read();      // trigger high-precision measurement, ~10ms
float sht40LastTempC();
float sht40LastHumidPct();
uint32_t sht40LastReadMs();
