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

## Tests et qualité

```bash
cd backend
pytest
ruff check .
ruff format .
```
