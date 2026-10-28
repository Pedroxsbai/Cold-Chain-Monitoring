# Cold Chain Monitoring

Surveillance de la température et de l'humidité des réfrigérateurs de laboratoire (2–8 °C),
avec détection des excursions, gestion d'incidents et escalade des alertes sur 3 niveaux.

Le cahier des charges complet se trouve dans [`docs/cahier-des-charges.md`](docs/cahier-des-charges.md).

## Structure du dépôt

| Dossier | Contenu |
| --- | --- |
| `backend/` | API Django + Django REST Framework, moteur d'incidents et d'escalade |
| `frontend/` | Application React (Vite) — *à venir* |
| `firmware/` | Firmware ESP8266 + DHT (C/C++ Arduino) |
| `docs/` | Cahier des charges, schémas, rapports |

Applications Django du backend :

| App | Rôle |
| --- | --- |
| `accounts` | Utilisateurs (connexion par e-mail), rôles, profil |
| `monitoring` | Frigos, nœuds IoT, mesures, chaînes d'escalade |
| `incidents` | Incidents, notifications, moteur d'escalade |
| `audit` | Journal d'événements |

## Installation du backend (développement)

Prérequis : Python 3.12+.

```bash
cd backend
python -m venv .venv
# Windows : .venv\Scripts\activate    Linux/macOS : source .venv/bin/activate
pip install -r requirements-dev.txt
```

Créer le fichier `backend/.env` (non versionné) :

```ini
DJANGO_SECRET_KEY=remplacer-par-une-longue-chaine-aleatoire
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_TIME_ZONE=Africa/Casablanca
CORS_ALLOWED_ORIGINS=http://localhost:5173

# E-mail : le backend console affiche les e-mails dans le terminal
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
# EMAIL_HOST=smtp.example.com
# EMAIL_PORT=587
# EMAIL_HOST_USER=
# EMAIL_HOST_PASSWORD=
# DEFAULT_FROM_EMAIL=coldchain@example.com

# Surveillance et escalade (durées en minutes, décimales acceptées)
OFFLINE_AFTER_MINUTES=45
CONSECUTIVE_OUT_OF_RANGE=2
NOTIFY_EVERY_MINUTES=20
ESCALATE_N2_AFTER_ROUNDS=4
ESCALATE_N3_AFTER_ROUNDS=8
SEVERITY_HOURS=5,8
RESUME_AFTER_ACK_MINUTES=120
TICK_SECONDS=30

# Notifications
NOTIFY_CHANNELS=ntfy,email
NTFY_SERVER=https://ntfy.sh
# NTFY_TOKEN=
ACK_LINK_MAX_AGE_HOURS=24
PUBLIC_BASE_URL=http://localhost:5173
API_BASE_URL=http://localhost:8000
```

Générer une clé secrète :

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Puis :

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

`createsuperuser` demande une adresse e-mail (pas de nom d'utilisateur) : la connexion se fait par e-mail.

Données de démonstration (3 comptes N1/N2/N3, un frigo, un nœud `FRIGO-LAB-01` dont la clé API
est affichée une seule fois) :

```bash
python manage.py seed_demo
```

La clé d'un nœud créé depuis l'admin est affichée une seule fois après l'enregistrement ;
l'action « Régénérer la clé API » en crée une nouvelle.

- Admin Django : http://localhost:8000/admin/
- Connexion JWT : `POST /api/auth/login/` avec `{"email": "...", "password": "..."}`

## API REST

Toutes les routes sont sous `/api/` et demandent un jeton JWT (`Authorization: Bearer <access>`),
sauf la réception des mesures (clé du nœud) et la réinitialisation du mot de passe.

| Méthode | Endpoint | Rôle | Accès |
| --- | --- | --- | --- |
| POST | `/api/measurements/` | Réception d'une mesure (`X-Device-Key` + `device_id` dans le JSON) | Nœud |
| GET | `/api/measurements/?fridge=&from=&to=&page=` | Historique paginé | Ses frigos |
| POST | `/api/auth/login/` · `refresh/` · `logout/` | Connexion (e-mail), renouvellement, déconnexion | Public / JWT |
| GET, PATCH | `/api/auth/me/` | Profil et canaux de notification | JWT |
| POST | `/api/auth/password/change/` | Changement de mot de passe | JWT |
| POST | `/api/auth/password/reset/` · `reset/confirm/` | Mot de passe oublié | Public |
| GET | `/api/fridges/` · `/api/fridges/{id}/` | Frigos + dernière mesure, statut, incident en cours | Ses frigos |
| GET | `/api/fridges/{id}/measurements/?from=&to=` | Série pour les graphiques (24 h par défaut) | Ses frigos |
| GET | `/api/fridges/{id}/measurements/export/?from=&to=` | Export CSV (`;`, virgule décimale) | Ses frigos |
| POST, PUT, PATCH, DELETE | `/api/fridges/` | Gestion des frigos | Admin |
| PATCH | `/api/fridges/{id}/thresholds/` | Seuils (journalisés) | Admin |
| GET | `/api/incidents/?fridge=&type=&status=&active=true&from=&to=` | Incidents | Ses frigos |
| POST | `/api/incidents/{id}/ack/` | Prise en charge | Chaîne du frigo |
| POST | `/api/incidents/{id}/comments/` | Commentaire | Chaîne du frigo |
| POST | `/api/incidents/{id}/close/` | Clôture avec commentaire (incident terminé) | N2 du frigo, Admin |
| CRUD | `/api/users/` · `/api/devices/` · `/api/escalation/` | Administration | Admin |
| POST | `/api/devices/{id}/rotate-key/` | Nouvelle clé de nœud (affichée une fois) | Admin |
| GET | `/api/events/?type=&actor=&from=&to=` | Journal d'événements | Admin |

`from` / `to` acceptent une date (`2026-10-28`) ou une date-heure ISO 8601.

Exemple d'envoi par un nœud :

```bash
curl -X POST http://localhost:8000/api/measurements/   -H "Content-Type: application/json" -H "X-Device-Key: <clé>"   -d '{"device_id": "FRIGO-LAB-01", "temperature": 5.2, "humidity": 48, "sensor_ok": true, "firmware": "1.0.0"}'
```

## Moteur d'alertes

Le serveur web enregistre les mesures et ouvre / termine les incidents. Un second processus,
le moteur d'alertes, tourne en permanence à côté : il détecte les nœuds silencieux, envoie
les notifications et gère l'escalade.

```bash
python manage.py run_alert_engine          # en continu (un cycle toutes les 30 s)
python manage.py run_alert_engine --once   # un seul cycle
```

Règles appliquées (cahier des charges §7) :

| Règle | Comportement |
| --- | --- |
| Ouverture | 2 mesures consécutives hors plage (`CONSECUTIVE_OUT_OF_RANGE`) ; 2 lectures capteur invalides ; nœud muet depuis 45 min |
| Unicité | Un seul incident en cours par frigo ; les mesures suivantes s'y rattachent (un nœud hors ligne qui revient hors plage transforme l'incident en incident de température) |
| Fin | Première mesure revenue dans la plage ; les personnes alertées reçoivent « retour à la normale » |
| Excursion | Temps cumulé hors plage, compté depuis la première mesure hors plage, affiché en direct avec le temps restant avant 10 h |
| Relances | Toutes les 20 min tant que personne n'a pris l'incident en charge |
| Escalade | N1 seul pour les 4 premières notifications, N1 + N2 de la 5ᵉ à la 8ᵉ, N1 + N2 + N3 ensuite |
| Gravité | À 5 h et 8 h d'excursion : alerte immédiate à tous les niveaux, même après prise en charge ; à 10 h : « réactifs compromis » |
| Reprise | Toujours en cours 2 h après la prise en charge : l'escalade reprend au niveau suivant |
| Personne dans la chaîne | Les administrateurs sont prévenus |

### Canaux

- **ntfy** : installer l'application ntfy sur le téléphone, s'abonner à un topic difficile à
  deviner (ex. `coldchain-labo-7f3k9`) et le renseigner dans le profil (`ntfy_topic`).
  La notification porte un bouton « Je prends en charge ».
- **E-mail** : le message contient le lien de prise en charge.

Chaque notification a son propre lien signé, valable 24 h et utilisable une seule fois.
Ouvrir le lien est enregistré mais n'arrête pas l'escalade : seule l'action « Je prends en
charge » le fait.

## Simulation

`scripts/simulate_node.py` se comporte comme un nœud ESP8266 (HTTP + clé) et rejoue un
incident complet en quelques minutes. Exemple de démo accélérée, dans trois terminaux :

Terminal 1 (serveur web) et terminal 2 (moteur), sous Windows cmd :

```bat
set NOTIFY_EVERY_MINUTES=0.5
set OFFLINE_AFTER_MINUTES=1
set TICK_SECONDS=5
python manage.py runserver
```

```bat
set NOTIFY_EVERY_MINUTES=0.5
set OFFLINE_AFTER_MINUTES=1
set TICK_SECONDS=5
python manage.py run_alert_engine
```

Terminal 3 (nœud simulé, avec la clé affichée par `seed_demo` ou l'admin) :

```bat
python scripts\simulate_node.py --key <clé> --scenario full --interval 10
```

Scénarios : `normal`, `excursion`, `sensor`, `offline`, `full`. Avec le backend e-mail
console, les e-mails s'affichent dans le terminal du moteur.

## Tests et qualité

```bash
cd backend
pytest
ruff check .
ruff format .
```
