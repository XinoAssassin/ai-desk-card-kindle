// HTTP server for v0.8 Wi-Fi transport. Three endpoints:
//
//   POST /frame          full frame (259200 bytes raw 4bpp)
//                        headers: X-Frame-Fid, X-Frame-CRC
//   POST /frame?x=&y=&w=&h=
//                        region update (w*h/2 bytes raw 4bpp)
//                        headers same as above
//   POST /cmd            JSON body, same dispatch as serial/BLE
//                        e.g. {"cmd":"restart"}
//   GET  /status         JSON: battery_pct, battery_mv, firmware, mac,
//                        uptime_s, wifi:{ssid,ip,rssi}
//
// The /frame handler writes pixels directly into frameBuffer() then calls
// frameDisplay(). Shares the PSRAM buffer with serial/BLE via the
// frameAcquireBuffer()/frameReleaseBuffer() lock.

#pragma once
#include <Arduino.h>

void httpServerStart();           // call after Wi-Fi connected
void httpServerStop();            // call when Wi-Fi goes down (battery mode)
void httpServerPoll();             // call in loop(); no-op if not started
bool httpServerRunning();
uint16_t httpServerPort();        // 9880 by default

// v0.9: outbound side. Pure ARCH A (Wi-Fi only) has no Serial/BLE backchannel,
// so the device must POST telemetry / touch events back to the daemon over
// Wi-Fi. The daemon IP is auto-discovered from the most recent inbound
// /frame or /cmd request.
const char* httpDaemonIp();                                 // "" if unknown
bool httpPostJsonToDaemon(const char* path, const char* json);
