# Firmware du nœud IoT

ESP8266 NodeMCU + DHT11 (ou DHT22). Le nœud lit température et humidité toutes les
20 minutes et les envoie en HTTP POST (JSON) à l'API, authentifié par sa clé.
Toute la logique (incidents, alertes) est sur le serveur.

| Fichier | Rôle |
| --- | --- |
| `cold_chain_node/cold_chain_node.ino` | Programme principal |
| `cold_chain_node/config.h` | Réglages : broche, type de capteur, intervalle, mode démo |
| `cold_chain_node/secrets.example.h` | Modèle à copier en `secrets.h` (Wi-Fi, URL, clé) — `secrets.h` n'est jamais versionné |
| `cold_chain_node/root_ca.h` | Certificat racine Let's Encrypt, pour le HTTPS en production |
| `examples/` | Premiers essais (lecture DHT seule, envoi simple) |

## 1. Câblage

Module DHT11 à 3 broches (résistance de tirage déjà présente sur le module) :

| DHT11 | NodeMCU |
| --- | --- |
| `+` / VCC | `3V3` |
| `-` / GND | `G` (GND) |
| `out` / DATA | `D1` (GPIO5) |

Capteur nu à 4 broches : ajouter une résistance de 10 kΩ entre DATA et VCC ; la broche 3
reste libre.

Alimentation : câble micro-USB vers une batterie externe (power bank) branchée sur
secteur, pour que le nœud continue d'émettre pendant une coupure de courant.

## 2. Arduino IDE (une seule fois)

1. **Carte ESP8266** : *Fichier > Préférences > URL de gestionnaire de cartes
   supplémentaires* : `https://arduino.esp8266.com/stable/package_esp8266com_index.json`,
   puis *Outils > Carte > Gestionnaire de cartes* : installer **esp8266** (3.1.x).
2. **Bibliothèques** (*Croquis > Inclure une bibliothèque > Gérer les bibliothèques*) :
   **DHT sensor library** (Adafruit) et **Adafruit Unified Sensor**. ArduinoJson n'est pas
   nécessaire.
3. **Pilote USB** : si aucun port COM n'apparaît, installer le pilote CH340 (ou CP2102,
   selon la puce écrite près du port USB).

## 3. Préparer le serveur pour le test local

Le nœud doit joindre le PC qui fait tourner Django sur le Wi-Fi :

1. Trouver l'IP du PC : `ipconfig` → *Adresse IPv4* (ex. `192.168.1.10`).
2. Dans `backend/.env`, ajouter cette IP aux hôtes autorisés :
   `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.10`
3. Lancer Django **sur toutes les interfaces** : `python manage.py runserver 0.0.0.0:8000`
4. Autoriser Python dans le pare-feu Windows (réseau **privé**) quand Windows le demande.
5. Vérifier depuis le téléphone, sur le même Wi-Fi : `http://192.168.1.10:8000/api/`
   doit répondre (une erreur 401 est normale : la page est protégée).
6. Déclarer le nœud dans l'application : *Administration > Nœuds IoT > Nouveau nœud*,
   rattaché à un frigo. Copier la clé affichée (une seule fois).

## 4. Configurer et téléverser le firmware

1. Ouvrir `firmware/cold_chain_node/cold_chain_node.ino` dans Arduino IDE.
2. Copier `secrets.example.h` en `secrets.h` dans le même dossier, puis le remplir :
   nom et mot de passe du Wi-Fi (2,4 GHz), `SERVER_URL`
   (`http://192.168.1.10:8000/api/measurements/`, **avec** la barre finale), `DEVICE_ID`
   et `DEVICE_KEY` exactement comme dans l'application.
3. Pour la démo, mettre `#define DEMO_MODE 1` dans `config.h` (une mesure toutes les
   30 s au lieu de 20 min). Le remettre à `0` pour l'installation réelle.
4. *Outils > Carte* : **NodeMCU 1.0 (ESP-12E Module)** ; *Outils > Port* : le port COM du
   NodeMCU ; *Upload Speed* : 115200 si le téléversement échoue en 921600.
5. Téléverser (flèche →). Si le téléversement bloque sur « Connecting… », maintenir le
   bouton **FLASH** du NodeMCU pendant quelques secondes.

## 5. Vérifier

*Outils > Moniteur série*, réglé sur **115200 bauds** :

```
Cold Chain node 1.0.0 — FRIGO-LAB-01 — mesure toutes les 30 s
[wifi] Connexion à "NOM_DU_WIFI"....
[wifi] Connecté, IP 192.168.1.42, signal -58 dBm
[dht] 22.4 °C · 41.0 %
[http] POST http://192.168.1.10:8000/api/measurements/ {"device_id":"FRIGO-LAB-01",...}
[http] 201 — mesure enregistrée
```

La mesure apparaît dans le tableau de bord (actualisé toutes les 30 s). La LED bleue
clignote une fois après un envoi réussi, cinq fois après un échec.

| Message | Cause probable |
| --- | --- |
| `[wifi] Échec` | Mauvais mot de passe, réseau 5 GHz, ou trop loin du point d'accès |
| `Erreur réseau : connection failed` | Mauvaise IP, Django lancé sans `0.0.0.0`, ou pare-feu |
| `Code HTTP 400` + `Bad Request` | IP du PC absente de `DJANGO_ALLOWED_HOSTS` |
| `Code HTTP 401` | `DEVICE_ID` ou `DEVICE_KEY` différent de l'application (régénérer la clé au besoin) |
| `Code HTTP 409` | Nœud non rattaché à un frigo dans l'administration |
| `[dht] Lecture invalide` répété | Câblage DATA / alimentation du capteur, ou mauvais `DHT_TYPE` |

## 6. Essais dans le frigo (plan de tests §13)

1. **Normal** : nœud dans le frigo, les mesures restent entre 2 et 8 °C.
2. **Excursion** : sortir le nœud ou laisser la porte ouverte : après 2 mesures hors
   plage, un incident s'ouvre et les alertes partent (moteur d'alertes lancé).
3. **Retour** : remettre au froid : l'incident se termine, « retour à la normale ».
4. **Coupure** : débrancher le nœud : après 45 min sans mesure, incident « nœud hors
   ligne ». En mode démo, régler `OFFLINE_AFTER_MINUTES=1` côté serveur pour le voir vite.

Note : le DHT11 mesure à ±2 °C et seulement à partir de 0 °C, ce qui est juste pour une
plage de 2–8 °C. Pour un usage réel, un DHT22 (`#define DHT_TYPE DHT22`, même câblage) ou
un SHT31 est recommandé.

## Production (HTTPS)

Avec `SERVER_URL = "https://votre-domaine/api/measurements/"`, le nœud synchronise son
horloge (NTP) puis vérifie le certificat du serveur avec la racine Let's Encrypt
(`root_ca.h`, valable jusqu'en 2035). Aucun autre réglage n'est nécessaire.
