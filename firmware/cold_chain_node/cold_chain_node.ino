/*
 * Cold Chain Monitoring — IoT node (ESP8266 NodeMCU + DHT11/DHT22).
 *
 * Every MEASUREMENT_INTERVAL_MS: read temperature and humidity, then POST
 *   {"device_id", "temperature", "humidity", "sensor_ok", "firmware"}
 * to the API with the per-node key in the X-Device-Key header. The server sets
 * the timestamp and does all the logic (incidents, alerts); the node stores nothing.
 *
 * - Wi-Fi: connects at boot and reconnects automatically when the link drops.
 * - Invalid sensor reading (NaN): reported with sensor_ok=false, not ignored.
 * - Network / server error: SEND_RETRIES more attempts, then wait for the next cycle.
 *
 * Libraries: "DHT sensor library" + "Adafruit Unified Sensor" (Adafruit).
 * Board: "NodeMCU 1.0 (ESP-12E Module)" from the esp8266 core.
 */

#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>
#include <WiFiClientSecureBearSSL.h>
#include <DHT.h>
#include <time.h>

#include "config.h"
#include "root_ca.h"
#include "secrets.h"

DHT dht(DHT_PIN, DHT_TYPE);
BearSSL::X509List trustAnchors(ROOT_CA);  // ISRG Root X1 + X2

unsigned long lastMeasurementAt = 0;
bool firstCycle = true;

struct Reading {
  bool ok;
  float temperature;
  float humidity;
};

// ---- Status LED (built-in LED is active low) ------------------------------

void ledOn() { digitalWrite(LED_BUILTIN, LOW); }
void ledOff() { digitalWrite(LED_BUILTIN, HIGH); }

void blink(int times, int ms) {
  for (int i = 0; i < times; i++) {
    ledOn();
    delay(ms);
    ledOff();
    delay(ms);
  }
}

// ---- Wi-Fi ----------------------------------------------------------------

bool ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return true;

  Serial.printf("[wifi] Connexion à \"%s\"", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
    delay(500);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.printf("[wifi] Échec (statut %d) — nouvel essai au prochain cycle\n", WiFi.status());
    return false;
  }
  Serial.printf("[wifi] Connecté, IP %s, signal %d dBm\n", WiFi.localIP().toString().c_str(),
                WiFi.RSSI());
  return true;
}

// ---- Time (needed to validate HTTPS certificates) -------------------------

bool isHttps() { return strncmp(SERVER_URL, "https://", 8) == 0; }

void syncClock() {
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  Serial.print("[ntp] Synchronisation de l'heure");
  unsigned long start = millis();
  // Any date after 2024 means the clock is set.
  while (time(nullptr) < 1704067200 && millis() - start < 15000) {
    delay(500);
    Serial.print('.');
  }
  Serial.println(time(nullptr) >= 1704067200 ? " OK" : " échec (HTTPS risque d'échouer)");
}

// ---- Sensor ---------------------------------------------------------------

Reading readSensor() {
  for (int attempt = 1; attempt <= SENSOR_READ_ATTEMPTS; attempt++) {
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();
    if (!isnan(humidity) && !isnan(temperature)) {
      return {true, temperature, humidity};
    }
    Serial.printf("[dht] Lecture invalide (essai %d/%d)\n", attempt, SENSOR_READ_ATTEMPTS);
    delay(SENSOR_RETRY_DELAY_MS);
  }
  return {false, NAN, NAN};
}

String buildPayload(const Reading& r) {
  // JSON has no NaN: a failed reading is sent as null with sensor_ok=false.
  String json = "{\"device_id\":\"";
  json += DEVICE_ID;
  json += "\",\"temperature\":";
  json += r.ok ? String(r.temperature, 1) : "null";
  json += ",\"humidity\":";
  json += r.ok ? String(r.humidity, 1) : "null";
  json += ",\"sensor_ok\":";
  json += r.ok ? "true" : "false";
  json += ",\"firmware\":\"" FIRMWARE_VERSION "\"}";
  return json;
}

// ---- HTTP -----------------------------------------------------------------

// Returns the HTTP status, or a negative HTTPClient error code.
int postOnce(const String& payload) {
  WiFiClient plainClient;
  BearSSL::WiFiClientSecure secureClient;
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);

  bool started;
  if (isHttps()) {
#if TLS_INSECURE
    secureClient.setInsecure();
#else
    secureClient.setTrustAnchors(&trustAnchors);
#endif
    // Default 16 kB receive buffer: hosting servers rarely accept smaller TLS fragments.
    started = http.begin(secureClient, SERVER_URL);
  } else {
    started = http.begin(plainClient, SERVER_URL);
  }
  if (!started) return HTTPC_ERROR_CONNECTION_FAILED;

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  int status = http.POST(payload);
  if (status > 0 && status != 201) {
    Serial.printf("[http] Réponse du serveur : %s\n", http.getString().c_str());
  }
  http.end();
  return status;
}

bool sendMeasurement(const String& payload) {
  for (int attempt = 0; attempt <= SEND_RETRIES; attempt++) {
    if (attempt > 0) {
      Serial.printf("[http] Nouvel essai %d/%d dans %lu s\n", attempt, SEND_RETRIES,
                    RETRY_DELAY_MS / 1000);
      delay(RETRY_DELAY_MS);
    }
    if (!ensureWifi()) continue;

    ledOn();
    int status = postOnce(payload);
    ledOff();

    if (status == 201) {
      Serial.println("[http] 201 — mesure enregistrée");
      return true;
    }
    if (status > 0) {
      Serial.printf("[http] Code HTTP %d\n", status);
      // 4xx: wrong key, unattached node, invalid data... retrying won't fix it.
      if (status >= 400 && status < 500) {
        if (status == 401) Serial.println("[http] Clé refusée : vérifiez DEVICE_ID et DEVICE_KEY");
        if (status == 409) Serial.println("[http] Nœud non rattaché à un frigo (admin)");
        return false;
      }
    } else {
      Serial.printf("[http] Erreur réseau : %s\n", HTTPClient::errorToString(status).c_str());
    }
  }
  return false;
}

// ---- Main -----------------------------------------------------------------

void measureAndSend() {
  Reading reading = readSensor();
  if (reading.ok) {
    Serial.printf("[dht] %.1f °C · %.1f %%\n", reading.temperature, reading.humidity);
  } else {
    Serial.println("[dht] Capteur en défaut : envoi de sensor_ok=false");
  }

  String payload = buildPayload(reading);
  Serial.printf("[http] POST %s %s\n", SERVER_URL, payload.c_str());
  if (sendMeasurement(payload)) {
    blink(1, 80);
  } else {
    Serial.println("[http] Abandon pour ce cycle — le serveur signalera le nœud hors ligne s'il reste muet");
    blink(5, 80);
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  ledOff();
  Serial.begin(115200);
  delay(100);
  Serial.printf("\n\nCold Chain node %s — %s — mesure toutes les %lu s\n", FIRMWARE_VERSION,
                DEVICE_ID, MEASUREMENT_INTERVAL_MS / 1000);

  dht.begin();

  WiFi.persistent(false);  // don't wear the flash rewriting credentials
  WiFi.setAutoReconnect(true);
  ensureWifi();
  if (isHttps()) syncClock();

  delay(2000);  // DHT warm-up before the first reading
}

void loop() {
  unsigned long now = millis();
  // Unsigned subtraction keeps working when millis() wraps around (~49 days).
  if (firstCycle || now - lastMeasurementAt >= MEASUREMENT_INTERVAL_MS) {
    firstCycle = false;
    lastMeasurementAt = now;
    measureAndSend();
    Serial.printf("[cycle] Prochaine mesure dans %lu s\n\n", MEASUREMENT_INTERVAL_MS / 1000);
  }
  delay(200);
}
