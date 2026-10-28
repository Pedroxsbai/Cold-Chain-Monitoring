// Copy this file to secrets.h (same folder) and fill it in.
// secrets.h is ignored by Git: never commit Wi-Fi passwords or device keys.
#pragma once

// Wi-Fi network of the lab (2.4 GHz: the ESP8266 does not support 5 GHz).
const char* WIFI_SSID     = "NOM_DU_WIFI";
const char* WIFI_PASSWORD = "MOT_DE_PASSE_WIFI";

// Measurement endpoint, with the trailing slash.
//   Local test : http://<IP of the PC running Django>:8000/api/measurements/
//   Production : https://<your domain>/api/measurements/
const char* SERVER_URL = "http://192.168.1.10:8000/api/measurements/";

// Shown once by the web app (Administration > Nœuds IoT) or by `manage.py seed_demo`.
const char* DEVICE_ID  = "FRIGO-LAB-01";
const char* DEVICE_KEY = "COLLER_ICI_LA_CLE_DU_NOEUD";
