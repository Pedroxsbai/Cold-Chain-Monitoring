# Cahier des charges — Cold Chain Monitoring

Oct 28, 2026&#32;

## 1. Contexte et problématique

Les réfrigérateurs de laboratoire contiennent des réactifs coûteux qui doivent rester entre **2 °C et 8 °C**. Au-delà de **10 heures cumulées hors de cette plage**, ils perdent leurs propriétés et deviennent inutilisables.

Les causes de dérive sont connues : coupure d'électricité, porte mal fermée, panne du compresseur, dégivrage défaillant. Aujourd'hui, rien ne prévient les responsables à temps.

Le projet **Cold Chain Monitoring** répond à ce besoin : mesurer en continu température et humidité, détecter les sorties de plage, et alerter les bons responsables selon une escalade à 3 niveaux jusqu'à ce que quelqu'un prenne l'incident en charge.

## 2. Objectifs

1. Surveiller en continu chaque frigo contenant des réactifs sensibles.
2. Mesurer la température et l'humidité, affichées sur **deux graphiques séparés**.
3. Conserver un historique complet des mesures et un journal des événements (logs).
4. Superviser l'état des nœuds IoT (en ligne / hors ligne).
5. Gérer les incidents de leur ouverture à leur clôture, avec escalade des alertes.
6. Donner à l'administrateur la gestion des rôles, des comptes, des seuils et de l'historique.

## 3. Périmètre et répartition de l'effort

L'essentiel du projet est l'application web ; le firmware est volontairement réduit.

| Volet | Poids | Contenu |
| --- | --- | --- |
| Application web | 95 % | Backend Django/DRF, frontend React, moteur d'alertes, base de données, déploiement sur serveur distant, tests |
| Firmware IoT | 5 % | Code C/C++ sur ESP8266 : lecture DHT, formatage JSON, envoi HTTP à l'API |
| Module IA de détection de pannes | Optionnel | Détection d'anomalies sur l'historique, hors périmètre du MVP |

**Hors périmètre :** application mobile native, stockage des données sur le nœud, intégration avec un logiciel de gestion de laboratoire existant.

## 4. Architecture globale

Le nœud ne fait que mesurer et envoyer ; toute la logique (stockage, détection, escalade) vit sur le serveur.

&#91;embedded content: architecture · nœud, serveur, clients\]

Le moteur d'alertes tourne indépendamment des requêtes : il détecte aussi l'absence de mesures (nœud hors ligne) et relance les notifications toutes les 20 minutes.

| Couche | Technologie |
| --- | --- |
| Nœud | ESP8266 NodeMCU + DHT11, firmware C/C++ (Arduino) |
| Transport | Wi-Fi, HTTP POST JSON (MQTT Mosquitto en option) |
| Backend | Django + Django REST Framework, SimpleJWT |
| Tâches planifiées | Celery Beat + Redis, ou APScheduler pour rester léger |
| Frontend | React (Vite), ApexCharts, tableaux interactifs |
| Base de données | SQLite |
| Déploiement | PC local, puis serveur Linux distant (Nginx, Gunicorn, HTTPS) |

## 5. Nœud IoT (boîtier)

Chaque frigo reçoit un boîtier autonome qui envoie une mesure toutes les 20 minutes. Le nœud ne stocke rien : toutes les données vivent sur le serveur.

**Matériel**

| Composant | Rôle |
| --- | --- |
| ESP8266 NodeMCU | Microcontrôleur Wi-Fi, exécute le firmware |
| Capteur DHT11 (voir §14) | Mesure température et humidité |
| Batterie tampon / power bank | Maintient le nœud actif pendant une coupure de courant |

**Exigences du firmware**

- Se connecter au Wi-Fi au démarrage et se reconnecter automatiquement en cas de perte.
- Lire température et humidité toutes les **20 minutes** (période configurable à la compilation).
- Construire un JSON et l'envoyer en **HTTP POST** à l'API, authentifié par une clé propre au nœud.
- En cas d'échec d'envoi, réessayer 3 fois avant d'attendre le cycle suivant.
- Une lecture invalide du capteur (NaN) est signalée au serveur, pas ignorée.

**Format du message**

```json
{
  "device_id": "FRIGO-LAB-01",
  "temperature": 5.2,
  "humidity": 48.0,
  "sensor_ok": true,
  "firmware": "1.0.0"
}
```

L'horodatage est posé par le serveur à la réception, ce qui évite de gérer une horloge sur l'ESP8266. La clé est transmise dans l'en-tête `X-Device-Key`.

**Choix HTTP plutôt que MQTT :** à une mesure toutes les 20 minutes, HTTP suffit, s'intègre directement à DRF et évite de déployer et sécuriser un broker Mosquitto. MQTT reste une évolution possible si le nombre de nœuds ou la fréquence augmente.

## 6. Fonctionnalités de l'application web

| Réf. | Module | Fonctionnalité | Priorité |
| --- | --- | --- | --- |
| F1 | Authentification | Connexion par e-mail et mot de passe, jeton JWT, déconnexion, mot de passe oublié | Must |
| F2 | Tableau de bord | Carte par frigo : dernière température, humidité, statut (normal / alerte / hors ligne), heure de la dernière mesure | Must |
| F3 | Graphiques | Un graphique ApexCharts pour la température et un autre pour l'humidité, plage 2–8 °C tracée en bande, filtres 24 h / 7 j / 30 j / personnalisé | Must |
| F4 | Historique | Tableau paginé des mesures, filtres par frigo et par date, export CSV | Must |
| F5 | Supervision des nœuds | Nœud marqué hors ligne si aucune mesure depuis 45 min (2 cycles + marge) ; génère une alerte | Must |
| F6 | Incidents | Ouverture automatique, prise en charge (acquittement), commentaire, clôture ; un seul incident ouvert par frigo | Must |
| F7 | Compteur d'excursion | Durée cumulée hors plage par incident, avec compte à rebours vers le seuil de 10 h | Must |
| F8 | Alertes et escalade | Notifications répétées toutes les 20 min, escalade sur 3 niveaux (§7) | Must |
| F9 | Acquittement sur téléphone | Bouton « Je prends en charge » dans la notification et sur une page web mobile | Must |
| F10 | Journal d'événements | Trace horodatée de chaque action : mesure hors plage, alerte envoyée, acquittement, modification de seuil, connexion | Must |
| F11 | Administration | CRUD des utilisateurs, attribution des rôles, modification des numéros et informations personnelles | Must |
| F12 | Configuration des seuils | L'admin modifie la plage de température (et d'humidité) par frigo ; chaque changement est journalisé | Must |
| F13 | Gestion des frigos | CRUD des frigos, rattachement d'un nœud et d'une chaîne de responsables | Must |
| F14 | Profil | Chaque utilisateur modifie ses coordonnées et ses canaux de notification | Should |
| F15 | Détection de pannes IA | Détection d'anomalies (dérive lente, oscillations, capteur figé) sur l'historique | Could |

## 7. Gestion des incidents et escalade

Un incident s'ouvre dès qu'une mesure sort de la plage du frigo, et les notifications se répètent toutes les 20 minutes en élargissant les destinataires jusqu'à l'acquittement.

&#91;embedded content: escalade des alertes · 3 niveaux, 20 min entre deux notifications\]

Un seul niveau ne remplace jamais le précédent : chaque niveau s'ajoute, et N1 reste notifié jusqu'au bout.

**Règles**

1. **Ouverture :** une mesure hors plage ouvre un incident (seuil de 2 mesures consécutives activable contre les faux positifs). Types : température, humidité, nœud hors ligne, capteur défaillant.
2. **Unicité :** un seul incident ouvert par frigo ; les mesures suivantes s'y rattachent au lieu d'en créer de nouveaux.
3. **Acquittement :** uniquement par action explicite (bouton dans la notification ou dans l'application). La simple ouverture de la notification est enregistrée mais n'arrête pas l'escalade.
4. **Fin :** l'incident se termine automatiquement (`ended_at`) quand une mesure revient dans la plage. Une clôture avec commentaire par N2 ou l'admin reste demandée pour l'historique.
5. **Compteur d'excursion :** durée cumulée hors plage, affichée en direct avec le temps restant avant 10 h.
6. **Seuils de gravité (proposition) :** à 5 h puis 8 h d'excursion, alerte immédiate à tous les niveaux ; à 10 h, l'incident est marqué « réactifs compromis ».
7. **Reprise (proposition) :** si le frigo est toujours hors plage 2 h après l'acquittement, l'escalade reprend au niveau suivant.

**Question ouverte :** « mettre une vue » dans tes notes doit-il compter comme acquittement ? Le cahier propose de ne compter que l'action explicite, plus fiable.

## 8. Canaux de notification (sans Telegram)

Le système combine un canal principal gratuit avec bouton d'acquittement, et des canaux de renfort par SMS et appel pour les niveaux élevés.

| Canal | Usage | Coût | Acquittement possible |
| --- | --- | --- | --- |
| Notification push via **ntfy** (open source, auto-hébergeable) | Canal principal, tous niveaux | Gratuit | Oui, bouton d'action dans la notification |
| **E-mail** SMTP (compte du labo ou service transactionnel) | Tous niveaux, trace écrite | Gratuit | Oui, lien d'acquittement |
| **SMS** via passerelle Android (téléphone dédié + application passerelle open source) | Niveaux 2 et 3 | Forfait de la carte SIM | Oui, lien dans le SMS |
| **Appel vocal** via module GSM SIM800L relié au serveur (commande AT d'appel) | Niveau 3, et niveau 2 si l'incident dépasse 4 h | Forfait de la carte SIM | Non (l'appel réveille, l'acquittement se fait dans l'app) |

**Recommandation :** ntfy + e-mail couvrent le MVP gratuitement et de façon professionnelle. Le SMS et l'appel ne sont gratuits nulle part sans carte SIM ; la passerelle GSM est l'option la moins chère et ne dépend d'aucun service tiers. Une API payante (ex. Twilio) peut remplacer le module GSM si le budget le permet.

Chaque envoi est découplé du moteur d'alertes par une interface `Notifier`, pour ajouter ou changer un canal sans toucher à la logique d'escalade.

## 9. Rôles et permissions

| Action | Responsable frigo (N1) | Supérieur (N2) | Administrateur (N3) |
| --- | --- | --- | --- |
| Voir le tableau de bord et les graphiques de ses frigos | Oui | Oui | Oui (tous) |
| Acquitter et commenter un incident | Oui | Oui | Oui |
| Clôturer un incident | Non | Oui | Oui |
| Consulter l'historique et exporter | Ses frigos | Ses frigos | Tous |
| Modifier les seuils de température / humidité | Non | Non | Oui |
| Gérer frigos, nœuds et chaînes d'escalade | Non | Non | Oui |
| CRUD utilisateurs, rôles, numéros | Non | Non | Oui |
| Consulter le journal d'événements complet | Non | Non | Oui |

Un même utilisateur peut être N1 sur un frigo et N2 sur un autre : le niveau est porté par la chaîne d'escalade du frigo, le rôle global par le compte.

## 10. Modèle de données (SQLite)

| Table | Champs principaux | Remarque |
| --- | --- | --- |
| User | id, nom, prénom, email, téléphone, rôle, ntfy\_topic, actif | Étend l'utilisateur Django |
| Fridge | id, nom, emplacement, temp\_min, temp\_max, hum\_min, hum\_max, max\_excursion\_h (10) | Seuils modifiables par l'admin |
| Device | id, device\_id, fridge\_id, api\_key\_hash, last\_seen, firmware, statut | `last_seen` sert à la détection hors ligne |
| EscalationChain | fridge\_id, niveau (1–3), user\_id | Qui est notifié à chaque niveau |
| Measurement | id, device\_id, fridge\_id, temperature, humidity, sensor\_ok, received\_at | Index sur (fridge\_id, received\_at) |
| Incident | id, fridge\_id, type (temp / humidité / hors ligne / capteur), started\_at, ended\_at, statut, niveau\_actuel, nb\_notifs, acked\_by, acked\_at, excursion\_minutes | Contrainte : un seul incident ouvert par frigo |
| Notification | id, incident\_id, user\_id, canal, envoyée\_at, statut, lue\_at | Historique de chaque alerte envoyée |
| EventLog | id, horodatage, acteur, type, objet, détails (JSON) | Journal d'audit, en lecture seule |

SQLite convient au prototype et à quelques frigos. Le passage à PostgreSQL se fait sans modifier le code grâce à l'ORM Django.

## 11. API REST (Django REST Framework)

| Méthode | Endpoint | Rôle | Accès |
| --- | --- | --- | --- |
| POST | /api/measurements/ | Réception d'une mesure du nœud | Clé du nœud |
| POST | /api/auth/login/ · /api/auth/refresh/ | Connexion, renouvellement du jeton | Public / JWT |
| GET | /api/fridges/ · /api/fridges/{id}/ | Liste et détail des frigos avec dernier statut | JWT |
| GET | /api/fridges/{id}/measurements/?from=&to= | Séries pour les graphiques et l'historique | JWT |
| GET | /api/fridges/{id}/measurements/export/ | Export CSV | JWT |
| GET | /api/incidents/ · /api/incidents/{id}/ | Liste et détail des incidents | JWT |
| POST | /api/incidents/{id}/ack/ | Prise en charge (aussi via lien signé dans la notification) | JWT ou jeton signé |
| POST | /api/incidents/{id}/close/ | Clôture avec commentaire | N2, Admin |
| GET | /api/events/ | Journal d'événements | Admin |
| CRUD | /api/users/ · /api/devices/ · /api/escalation/ | Administration | Admin |
| PATCH | /api/fridges/{id}/thresholds/ | Modification des seuils | Admin |

## 12. Exigences non fonctionnelles

| Domaine | Exigence |
| --- | --- |
| Disponibilité | Le serveur et le moteur d'alertes tournent en service permanent et redémarrent seuls (systemd) |
| Délai d'alerte | Première notification envoyée moins de 1 min après réception d'une mesure hors plage |
| Sécurité | HTTPS obligatoire, mots de passe hachés, JWT à durée courte, clé API par nœud, liens d'acquittement signés et à usage unique |
| Traçabilité | Toute action et toute modification de seuil est inscrite dans le journal, non modifiable |
| Conservation | Mesures conservées au moins 1 an ; sauvegarde quotidienne du fichier SQLite |
| Ergonomie | Interface responsive, utilisable sur téléphone pour l'acquittement |
| Langue | Interface en français |
| Maintenabilité | Code versionné sous Git, tests automatisés du moteur d'escalade, README d'installation |

## 13. Déploiement et tests

**Environnements**

1. **Développement local :** Django `runserver` + React (Vite), nœud pointant vers l'IP du PC sur le réseau local.
2. **Serveur distant :** VPS Linux, Nginx en reverse proxy + Gunicorn, build React servi en statique, certificat HTTPS Let's Encrypt, tâches planifiées par systemd ou Celery Beat.

**Plan de tests**

| Type | Ce qui est testé | Outil |
| --- | --- | --- |
| Unitaires | Ouverture / clôture d'incident, calcul de l'excursion, règles d'escalade (4 et 8 notifs) | pytest-django |
| API | Endpoints, permissions par rôle, rejet d'une clé de nœud invalide | DRF APIClient |
| Simulation | Script qui envoie de fausses mesures (normale, hors plage, silence) pour rejouer un incident complet | Script Python |
| Intégration matériel | Nœud réel posé dans un frigo, puis réchauffé, puis débranché | ESP8266 + DHT |
| Bout en bout | Réception effective des notifications ntfy, e-mail, SMS, appel et acquittement depuis le téléphone | Manuel |

Le script de simulation permet de tester 95 % du système sans attendre des cycles réels de 20 minutes : l'intervalle est paramétrable en mode test.

## 14. Points d'attention et risques

| Risque | Impact | Mesure proposée |
| --- | --- | --- |
| **Précision du DHT11** : ±2 °C, et plage de mesure à partir de 0 °C seulement | Sur une plage de 2–8 °C, une erreur de 2 °C peut masquer ou inventer une excursion | Garder le DHT11 pour le prototype ; prévoir DHT22 ou SHT31 (±0,3–0,5 °C) pour un usage réel. À valider avec l'encadrant |
| Coupure de courant du frigo | Le nœud s'éteint aussi et ne peut plus rien signaler | Batterie tampon sur le nœud ; à défaut, l'alerte « nœud hors ligne » sert de détection de coupure |
| Mesure toutes les 20 min | Une excursion est détectée jusqu'à 20 min en retard | Acceptable face au seuil de 10 h ; intervalle configurable si besoin |
| Wi-Fi du labo indisponible | Perte de mesures | Alerte hors ligne ; option : mise en mémoire de quelques mesures sur l'ESP et renvoi groupé |
| Faux positifs à l'ouverture de porte | Alertes inutiles, lassitude des responsables | Ouvrir l'incident après 2 mesures consécutives hors plage (paramétrable) |
| Panne du serveur | Plus aucune alerte | Service redémarré automatiquement + supervision externe gratuite du serveur (ping HTTP) |
| SMS / appels non gratuits | Coût récurrent | ntfy + e-mail pour le MVP ; GSM en option |

## 15. Planning et livrables

| Phase | Contenu | Durée indicative |
| --- | --- | --- |
| 1. Conception | Validation du cahier des charges, maquettes, modèle de données | 1 semaine |
| 2. Backend | Modèles, API DRF, authentification, moteur d'incidents et d'escalade, tests | 3 semaines |
| 3. Frontend | Tableau de bord, graphiques ApexCharts, historique, incidents, administration | 3 semaines |
| 4. Notifications | ntfy, e-mail, page d'acquittement mobile ; SMS / appel en option | 1 semaine |
| 5. Firmware | Lecture DHT, JSON, POST HTTP, reconnexion Wi-Fi | 3 jours |
| 6. Déploiement et tests | Serveur distant, HTTPS, simulation, essais réels dans un frigo | 1 semaine |

Les durées sont indicatives et à ajuster selon ta date de rendu.

**Livrables**

- [ ] Code source backend, frontend et firmware sur un dépôt Git
- [ ] Application déployée et accessible sur le serveur distant
- [ ] Nœud IoT fonctionnel envoyant ses mesures
- [ ] Script de simulation et rapport de tests
- [ ] Guide d'installation et manuel utilisateur
- [ ] Rapport du projet et démonstration
