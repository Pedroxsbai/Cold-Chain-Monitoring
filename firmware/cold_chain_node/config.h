// Cold Chain Monitoring node — compile-time settings (no secrets here).
// Wi-Fi, server URL and device key go in secrets.h (copy secrets.example.h).
#pragma once

#define FIRMWARE_VERSION "1.0.0"

// ---- Sensor ---------------------------------------------------------------
// DHT11 for the prototype; DHT22 (±0.5 °C) is recommended for real use.
#define DHT_TYPE DHT11
#define DHT_PIN D1  // GPIO5

// ---- Timing ---------------------------------------------------------------
// One measurement every 20 minutes (cahier des charges §5).
// For a demo, set DEMO_MODE to 1: one measurement every 30 seconds.
#define DEMO_MODE 0

#if DEMO_MODE
#define MEASUREMENT_INTERVAL_MS (30UL * 1000UL)
#else
#define MEASUREMENT_INTERVAL_MS (20UL * 60UL * 1000UL)
#endif

// On failure, retry the POST this many times before waiting for the next cycle.
#define SEND_RETRIES 3
#define RETRY_DELAY_MS 5000UL
#define HTTP_TIMEOUT_MS 10000

// The DHT sometimes returns NaN: re-read a few times before reporting a failure.
#define SENSOR_READ_ATTEMPTS 3
#define SENSOR_RETRY_DELAY_MS 2500UL

// Give up a Wi-Fi (re)connection attempt after this delay; the next cycle retries.
#define WIFI_CONNECT_TIMEOUT_MS 30000UL

// ---- HTTPS ----------------------------------------------------------------
// With an https:// SERVER_URL the server certificate is checked against the
// Let's Encrypt root (root_ca.h). Set to 1 only to debug a TLS problem.
#define TLS_INSECURE 0
