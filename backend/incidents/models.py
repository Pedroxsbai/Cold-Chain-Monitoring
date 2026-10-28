from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from monitoring.models import Fridge


class Incident(models.Model):
    """An excursion or failure on a fridge, from detection to closure.

    Lifecycle: OPEN → ACKNOWLEDGED (someone takes charge) → ENDED (back in
    range, `ended_at` set automatically) → CLOSED (comment by N2 / admin).
    Only one incident per fridge may be unfinished (`ended_at` is null).
    """

    class Type(models.TextChoices):
        TEMPERATURE = "temperature", "Température"
        HUMIDITY = "humidity", "Humidité"
        OFFLINE = "offline", "Nœud hors ligne"
        SENSOR = "sensor", "Capteur défaillant"

    class Status(models.TextChoices):
        OPEN = "open", "Ouvert"
        ACKNOWLEDGED = "acknowledged", "Pris en charge"
        ENDED = "ended", "Terminé"
        CLOSED = "closed", "Clôturé"

    fridge = models.ForeignKey(
        Fridge, verbose_name="frigo", on_delete=models.PROTECT, related_name="incidents"
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    started_at = models.DateTimeField("début", default=timezone.now)
    ended_at = models.DateTimeField("fin", null=True, blank=True)

    # Escalation
    current_level = models.PositiveSmallIntegerField("niveau actuel", default=1)
    notification_count = models.PositiveIntegerField("notifications envoyées", default=0)
    last_notified_at = models.DateTimeField("dernière notification", null=True, blank=True)

    # Acknowledgement
    acked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="pris en charge par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acked_incidents",
    )
    acked_at = models.DateTimeField("pris en charge le", null=True, blank=True)

    # Excursion
    excursion_minutes = models.FloatField("durée hors plage (min)", default=0)
    severity_hours_reached = models.PositiveSmallIntegerField(
        "dernier seuil de gravité atteint (h)", default=0
    )
    reagents_compromised = models.BooleanField("réactifs compromis", default=False)

    # Closure
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="clôturé par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_incidents",
    )
    closed_at = models.DateTimeField("clôturé le", null=True, blank=True)
    closing_comment = models.TextField("commentaire de clôture", blank=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["fridge"],
                condition=Q(ended_at__isnull=True),
                name="incident_one_unfinished_per_fridge",
                violation_error_message="Un incident est déjà en cours sur ce frigo.",
            ),
        ]
        indexes = [models.Index(fields=["status"], name="incident_status_idx")]

    def __str__(self):
        return f"#{self.pk} {self.fridge} · {self.get_type_display()} · {self.get_status_display()}"

    @property
    def is_finished(self):
        return self.ended_at is not None

    @property
    def remaining_minutes(self):
        """Minutes left before the reagents are considered compromised."""
        return max(0.0, self.fridge.max_excursion_hours * 60 - self.excursion_minutes)


class IncidentComment(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    text = models.TextField("commentaire")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "commentaire"
        ordering = ["created_at"]

    def __str__(self):
        return f"Commentaire #{self.pk} sur incident #{self.incident_id}"


class Notification(models.Model):
    """One alert sent to one user on one channel."""

    class Channel(models.TextChoices):
        NTFY = "ntfy", "Notification push (ntfy)"
        EMAIL = "email", "E-mail"
        SMS = "sms", "SMS"
        CALL = "call", "Appel vocal"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        SENT = "sent", "Envoyée"
        FAILED = "failed", "Échec"

    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="notifications")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="notifications"
    )
    channel = models.CharField("canal", max_length=10, choices=Channel.choices)
    level = models.PositiveSmallIntegerField("niveau", default=1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField("envoyée le", null=True, blank=True)
    read_at = models.DateTimeField("lue le", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_channel_display()} → {self.user} (incident #{self.incident_id})"
