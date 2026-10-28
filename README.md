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

# Surveillance
MEASUREMENT_INTERVAL_MINUTES=20
OFFLINE_AFTER_MINUTES=45
NOTIFY_EVERY_MINUTES=20
CONSECUTIVE_OUT_OF_RANGE=2
NTFY_SERVER=https://ntfy.sh
PUBLIC_BASE_URL=http://localhost:5173
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

## Tests et qualité

```bash
cd backend
pytest
ruff check .
ruff format .
```
