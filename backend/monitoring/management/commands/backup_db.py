import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Sauvegarde la base SQLite (copie cohérente, même pendant l'écriture) et ne garde "
        "que les BACKUP_KEEP dernières. À lancer une fois par jour."
    )

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("backup_db ne gère que SQLite.")
        backup_dir = Path(settings.COLDCHAIN["BACKUP_DIR"])
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = backup_dir / f"db-{timezone.localtime():%Y%m%d-%H%M}.sqlite3"

        # sqlite3's online backup API copies a consistent snapshot without locking writers out.
        connection.ensure_connection()
        dest = sqlite3.connect(target)
        try:
            connection.connection.backup(dest)
        finally:
            dest.close()

        keep = settings.COLDCHAIN["BACKUP_KEEP"]
        backups = sorted(backup_dir.glob("db-*.sqlite3"))
        for old in backups[:-keep] if keep > 0 else []:
            old.unlink()

        size_kb = target.stat().st_size // 1024
        self.stdout.write(self.style.SUCCESS(f"Sauvegarde : {target} ({size_kb} Ko)"))
