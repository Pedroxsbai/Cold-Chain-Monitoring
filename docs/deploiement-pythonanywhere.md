# Déploiement sur PythonAnywhere (compte gratuit)

Tout tient dans **une seule application web Django** sur `https://USERNAME.pythonanywhere.com` :
l'API, l'admin Django et l'interface React (servie par WhiteNoise). Le moteur d'alertes, qui
ne peut pas tourner en permanence sur un compte gratuit, est déclenché **chaque minute** par
**cron-job.org** via `POST /api/engine/tick/`. La sauvegarde SQLite quotidienne utilise la
tâche planifiée gratuite de PythonAnywhere.

```
ESP8266 ──HTTPS──┐
Navigateur ──────┼──> USERNAME.pythonanywhere.com  (Django + React, SQLite)
cron-job.org ────┘        │  chaque minute : /api/engine/tick/
                          └──> ntfy.sh (push)  ·  smtp.gmail.com (e-mail)
```

> Écart avec le cahier des charges §13 (VPS + Nginx + Gunicorn + systemd) : à justifier dans
> le rapport — hébergement gratuit, HTTPS inclus, aucune administration système ; le
> moteur passe d'un service permanent à un cycle déclenché chaque minute (délai d'alerte
> toujours < 1 min).

Dans tout ce guide, remplacer **`USERNAME`** par votre nom d'utilisateur PythonAnywhere.
Comptes créés sur eu.pythonanywhere.com : le domaine est `USERNAME.eu.pythonanywhere.com`.

---

## 1. Créer le compte

1. https://www.pythonanywhere.com → *Pricing & signup* → **Create a Beginner account**.
2. Le nom d'utilisateur devient l'adresse du site : choisissez-le en conséquence
   (ex. `coldchainlabo` → `https://coldchainlabo.pythonanywhere.com`).
3. Confirmez l'e-mail.

## 2. Récupérer le code (console Bash)

Onglet **Consoles** → **Bash** :

```bash
git clone https://github.com/Pedroxsbai/Cold-Chain-Monitoring.git
cd Cold-Chain-Monitoring
mkvirtualenv --python=python3.12 coldchain
pip install -r backend/requirements.txt
```

`mkvirtualenv` active l'environnement (l'invite commence par `(coldchain)`). Dans une
nouvelle console, le réactiver avec `workon coldchain`.

Si `python3.12` n'existe pas, `ls /usr/bin/python3.*` liste les versions disponibles :
prendre la plus récente ≥ 3.10.

## 3. Le fichier `.env` de production

Générer deux secrets :

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"   # DJANGO_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"   # ENGINE_TICK_TOKEN
```

Puis `nano ~/Cold-Chain-Monitoring/backend/.env` et coller (remplacer les valeurs) :

```ini
DJANGO_SECRET_KEY=<premier secret>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=USERNAME.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://USERNAME.pythonanywhere.com
CORS_ALLOWED_ORIGINS=https://USERNAME.pythonanywhere.com
DJANGO_TIME_ZONE=Africa/Casablanca

PUBLIC_BASE_URL=https://USERNAME.pythonanywhere.com
API_BASE_URL=https://USERNAME.pythonanywhere.com
ENGINE_TICK_TOKEN=<second secret>

NOTIFY_CHANNELS=ntfy,email
NTFY_SERVER=https://ntfy.sh

# E-mail via Gmail (seul SMTP autorisé sur un compte gratuit) — voir étape 9
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=votre.adresse@gmail.com
EMAIL_HOST_PASSWORD=<mot de passe d'application Gmail>
DEFAULT_FROM_EMAIL=Cold Chain <votre.adresse@gmail.com>
```

`Ctrl+O`, `Entrée`, `Ctrl+X` pour enregistrer. Ce fichier ne quitte jamais le serveur.

## 4. Base de données et fichiers statiques

```bash
cd ~/Cold-Chain-Monitoring/backend
python manage.py migrate
python manage.py createsuperuser        # e-mail + mot de passe : le compte administrateur
python manage.py collectstatic --noinput
```

## 5. Construire et envoyer l'interface React (depuis votre PC)

PythonAnywhere n'a pas de Node.js récent : on construit sur le PC et on envoie le résultat.

Dans PowerShell, sur le PC :

```powershell
cd C:\5GI\IoT\Projet\frontend
npm install
npm run build
tar -a -cf dist.zip dist
```

Sur PythonAnywhere, onglet **Files** → dossier `/home/USERNAME/Cold-Chain-Monitoring/frontend/`
→ **Upload a file** → `dist.zip`. Puis dans la console Bash :

```bash
cd ~/Cold-Chain-Monitoring/frontend && rm -rf dist && unzip -q dist.zip && rm dist.zip && ls dist
```

`ls` doit afficher `assets  favicon.svg  index.html`.

## 6. Créer l'application web

Onglet **Web** → **Add a new web app** → *Next* → **Manual configuration** (pas l'assistant
Django) → même version de Python qu'à l'étape 2.

Sur la page de configuration de l'application :

| Réglage | Valeur |
| --- | --- |
| Source code | `/home/USERNAME/Cold-Chain-Monitoring/backend` |
| Working directory | `/home/USERNAME/Cold-Chain-Monitoring/backend` |
| Virtualenv | `/home/USERNAME/.virtualenvs/coldchain` |
| Force HTTPS | **Enabled** |

Cliquer sur le lien **WSGI configuration file**, tout effacer et coller le contenu de
[`deploy/pythonanywhere_wsgi.py`](../deploy/pythonanywhere_wsgi.py) en remplaçant
`USERNAME`. Enregistrer.

Rien à mettre dans *Static files* : WhiteNoise sert l'interface et l'admin.

En haut de la page : **Reload USERNAME.pythonanywhere.com**.

Vérifier :

- `https://USERNAME.pythonanywhere.com/` → page de connexion de l'application ;
- `https://USERNAME.pythonanywhere.com/admin/` → admin Django (connexion par e-mail).

En cas de page d'erreur : onglet **Web** → *Log files* → **error log** (dernières lignes).

## 7. Configurer les frigos

Dans l'application (compte administrateur) : *Frigos* → créer les frigos, *Utilisateurs* →
créer N1 / N2 / N3, *Frigos* → **Chaîne** pour chaque frigo, *Nœuds IoT* → créer
`FRIGO-LAB-01` rattaché à son frigo et **copier la clé** (affichée une seule fois).

## 8. Déclencher le moteur d'alertes chaque minute (cron-job.org)

1. Créer un compte gratuit sur https://cron-job.org.
2. **Create cronjob** :
   - *Title* : `Cold Chain tick`
   - *URL* : `https://USERNAME.pythonanywhere.com/api/engine/tick/`
   - *Execution schedule* : **Every minute**
   - onglet **Advanced** : *Request method* **POST** ; *Headers* → ajouter
     `X-Engine-Token` = le `ENGINE_TICK_TOKEN` du `.env` ; *Timeout* : 30 s.
3. Enregistrer, puis **Test run** : la réponse doit être `200` avec
   `{"ok": true, ...}`. Un `403` signale un jeton différent de celui du `.env`.
4. Laisser activée la notification d'échec de cron-job.org : elle sert de supervision
   externe du serveur (§14, « panne du serveur »).

## 9. Notifications

**ntfy (canal principal)** — rien à configurer côté serveur. Chaque utilisateur installe
l'application ntfy, s'abonne à un topic difficile à deviner et le saisit dans *Mon profil*.

**E-mail via Gmail** — les comptes gratuits ne peuvent envoyer des e-mails que par Gmail :

1. Compte Google → *Sécurité* → activer la **validation en deux étapes**.
2. *Sécurité* → **Mots de passe des applications** → créer « Cold Chain » → copier le code
   de 16 lettres dans `EMAIL_HOST_PASSWORD` (sans espaces).
3. **Reload** de l'application web, puis tester dans la console Bash :

   ```bash
   cd ~/Cold-Chain-Monitoring/backend && python manage.py sendtestemail votre.adresse@gmail.com
   ```

Si l'envoi échoue sur le compte gratuit, mettre `NOTIFY_CHANNELS=ntfy` : ntfy reste le
canal d'alerte avec bouton de prise en charge.

## 10. Sauvegarde quotidienne

Onglet **Tasks** → *Scheduled tasks* (1 tâche quotidienne gratuite), heure `03:00`,
commande :

```
/home/USERNAME/.virtualenvs/coldchain/bin/python /home/USERNAME/Cold-Chain-Monitoring/backend/manage.py backup_db
```

Les 14 dernières copies sont gardées dans `backend/backups/` (téléchargeables depuis
l'onglet **Files**).

## 11. Brancher le nœud

Dans `firmware/cold_chain_node/secrets.h` (sur le PC, jamais sur GitHub) :

```c
const char* SERVER_URL = "https://USERNAME.pythonanywhere.com/api/measurements/";
const char* DEVICE_ID  = "FRIGO-LAB-01";
const char* DEVICE_KEY = "<clé copiée à l'étape 7>";
```

Mettre `DEMO_MODE 0` dans `config.h`, téléverser, et vérifier au moniteur série
(115200 bauds) : `[ntp] ... OK` puis `[http] 201 — mesure enregistrée`. Le certificat de
PythonAnywhere (Let's Encrypt) est vérifié grâce aux racines de `root_ca.h`.

## 12. Garder le site en ligne

Un site gratuit est désactivé au bout de 3 mois sans visite de l'onglet **Web** :
PythonAnywhere prévient par e-mail ; cliquer alors sur **Run until 3 months from today**.

## Mettre à jour après un `git push`

Console Bash :

```bash
cd ~/Cold-Chain-Monitoring && git pull
workon coldchain && pip install -r backend/requirements.txt
cd backend && python manage.py migrate && python manage.py collectstatic --noinput
```

Si le frontend a changé : refaire l'étape 5. Puis **Reload** dans l'onglet **Web**.

## Dépannage

| Symptôme | Piste |
| --- | --- |
| « Something went wrong » | *Web* → *error log* ; souvent une variable manquante dans `.env` |
| `DisallowedHost` / 400 | `DJANGO_ALLOWED_HOSTS` doit contenir exactement le domaine |
| Admin : erreur CSRF à la connexion | `CSRF_TRUSTED_ORIGINS=https://USERNAME.pythonanywhere.com` |
| Page « Interface non installée » (503) | Étape 5 : `frontend/dist/index.html` absent |
| cron-job.org : 404 | `ENGINE_TICK_TOKEN` vide ou application non rechargée |
| cron-job.org : 403 | En-tête `X-Engine-Token` différent du `.env` |
| Nœud : `Code HTTP 401` | `DEVICE_ID` / `DEVICE_KEY` différents de la base de production |
| Nœud : erreur réseau en HTTPS | Horloge non synchronisée (`[ntp] échec`) : vérifier l'accès Internet du Wi-Fi |
