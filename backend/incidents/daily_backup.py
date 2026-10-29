"""Sauvegarde quotidienne de la base SQLite, déclenchée par le tick du moteur.

Les tâches planifiées ne sont pas disponibles sur un compte PythonAnywhere gratuit.
cron-job.org appelle déjà /api/engine/tick/ chaque minute : le premier tick après
BACKUP_HOUR (heure locale) lance la commande backup_db, une seule fois par jour.
"""

import io
import logging
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

logger = logging.getLogger(__name__)

BACKUP_HOUR = 3  # heure locale à partir de laquelle la sauvegarde du jour est faite


def daily_backup_if_due():
    """Lance backup_db si l'heure est passée et qu'aucune sauvegarde n'existe aujourd'hui.

    Renvoie True si une sauvegarde vient d'être faite, False sinon.
    Ne lève jamais d'exception : une sauvegarde ratée ne doit pas bloquer le moteur d'alertes.
    """
    try:
        now = timezone.localtime()
        if now.hour < BACKUP_HOUR:
            return False

        backup_dir = Path(settings.COLDCHAIN["BACKUP_DIR"])
        if backup_dir.exists():
            tz = timezone.get_current_timezone()
            for f in backup_dir.glob("db-*.sqlite3"):
                if datetime.fromtimestamp(f.stat().st_mtime, tz=tz).date() == now.date():
                    return False  # déjà sauvegardé aujourd'hui

        call_command("backup_db", stdout=io.StringIO())
        logger.info("Sauvegarde quotidienne effectuée")
        return True
    except Exception:
        logger.exception("Sauvegarde quotidienne échouée")
        return False