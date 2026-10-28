from django.conf import settings
from django.db import models
from django.utils import timezone


class EventLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionError("Le journal d'événements est en lecture seule.")

    def delete(self):
        raise PermissionError("Le journal d'événements est en lecture seule.")


class EventLog(models.Model):
    """Append-only audit trail. Rows can be created, never modified or deleted.

    Write entries through `audit.services.log_event`.
    """

    class Type(models.TextChoices):
        # Measurements and nodes
        MEASUREMENT_OUT_OF_RANGE = "measurement_out_of_range", "Mesure hors plage"
        SENSOR_FAILURE = "sensor_failure", "Lecture capteur invalide"
        DEVICE_OFFLINE = "device_offline", "Nœud hors ligne"
        DEVICE_ONLINE = "device_online", "Nœud de nouveau en ligne"
        DEVICE_KEY_REJECTED = "device_key_rejected", "Clé de nœud refusée"
        # Incidents
        INCIDENT_OPENED = "incident_opened", "Incident ouvert"
        INCIDENT_ESCALATED = "incident_escalated", "Incident escaladé"
        INCIDENT_ACKED = "incident_acked", "Incident pris en charge"
        INCIDENT_COMMENTED = "incident_commented", "Commentaire ajouté"
        INCIDENT_ENDED = "incident_ended", "Incident terminé"
        INCIDENT_CLOSED = "incident_closed", "Incident clôturé"
        REAGENTS_COMPROMISED = "reagents_compromised", "Réactifs compromis"
        # Notifications
        NOTIFICATION_SENT = "notification_sent", "Notification envoyée"
        NOTIFICATION_FAILED = "notification_failed", "Échec de notification"
        NOTIFICATION_READ = "notification_read", "Notification lue"
        # Administration
        THRESHOLD_CHANGED = "threshold_changed", "Seuil modifié"
        OBJECT_CREATED = "object_created", "Création"
        OBJECT_UPDATED = "object_updated", "Modification"
        OBJECT_DELETED = "object_deleted", "Suppression"
        # Authentication
        USER_LOGIN = "user_login", "Connexion"
        USER_LOGIN_FAILED = "user_login_failed", "Échec de connexion"
        PASSWORD_RESET = "password_reset", "Réinitialisation du mot de passe"

    timestamp = models.DateTimeField("horodatage", default=timezone.now, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="acteur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # Kept even if the user is deleted; also used for "system" or a device id.
    actor_label = models.CharField("acteur (libellé)", max_length=150, blank=True)
    type = models.CharField(max_length=40, choices=Type.choices, db_index=True)
    object_type = models.CharField("type d'objet", max_length=50, blank=True)
    object_id = models.CharField("id de l'objet", max_length=50, blank=True)
    object_repr = models.CharField("objet", max_length=200, blank=True)
    details = models.JSONField("détails", default=dict, blank=True)

    objects = EventLogQuerySet.as_manager()

    class Meta:
        verbose_name = "événement"
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["object_type", "object_id"], name="event_object_idx")]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} · {self.get_type_display()} · {self.object_repr}"

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            raise PermissionError("Le journal d'événements est en lecture seule.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Le journal d'événements est en lecture seule.")
