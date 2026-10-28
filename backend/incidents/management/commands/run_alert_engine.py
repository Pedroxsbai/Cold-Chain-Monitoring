import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from incidents import engine

logger = logging.getLogger("incidents")


def run_tick():
    close_old_connections()
    try:
        engine.tick()
    except Exception:
        logger.exception("Échec du cycle du moteur d'alertes")
    finally:
        close_old_connections()


class Command(BaseCommand):
    help = (
        "Lance le moteur d'alertes : détection des nœuds hors ligne, escalade et "
        "notifications. À exécuter en service permanent (systemd) à côté du serveur web."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--once", action="store_true", help="Exécute un seul cycle puis quitte."
        )

    def handle(self, *args, once=False, **options):
        if once:
            run_tick()
            return

        seconds = settings.COLDCHAIN["TICK_SECONDS"]
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_job(
            run_tick,
            "interval",
            seconds=seconds,
            id="alert_engine_tick",
            max_instances=1,
            coalesce=True,
            next_run_time=timezone.now(),
        )
        self.stdout.write(f"Moteur d'alertes démarré (cycle de {seconds} s). Ctrl+C pour arrêter.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown(wait=False)
            self.stdout.write("Moteur d'alertes arrêté.")
