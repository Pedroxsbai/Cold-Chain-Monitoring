import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Fridge(models.Model):
    """A monitored fridge and its acceptable ranges."""

    name = models.CharField("nom", max_length=100, unique=True)
    location = models.CharField("emplacement", max_length=200, blank=True)
    temp_min = models.FloatField("température min (°C)", default=2.0)
    temp_max = models.FloatField("température max (°C)", default=8.0)
    hum_min = models.FloatField("humidité min (%)", null=True, blank=True)
    hum_max = models.FloatField("humidité max (%)", null=True, blank=True)
    max_excursion_hours = models.PositiveSmallIntegerField("durée max hors plage (h)", default=10)
    is_active = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "frigo"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(temp_min__lt=F("temp_max")), name="fridge_temp_min_lt_max"
            ),
            models.CheckConstraint(
                condition=Q(hum_min__isnull=True)
                | Q(hum_max__isnull=True)
                | Q(hum_min__lt=F("hum_max")),
                name="fridge_hum_min_lt_max",
            ),
        ]

    def __str__(self):
        return self.name

    def is_temperature_in_range(self, value):
        return self.temp_min <= value <= self.temp_max

    def is_humidity_in_range(self, value):
        if self.hum_min is not None and value < self.hum_min:
            return False
        return not (self.hum_max is not None and value > self.hum_max)


class Device(models.Model):
    """An IoT node (ESP8266 + DHT) attached to a fridge.

    The node authenticates with a per-device key sent in the `X-Device-Key`
    header; only its hash is stored.
    """

    class Status(models.TextChoices):
        UNKNOWN = "unknown", "Inconnu"
        ONLINE = "online", "En ligne"
        OFFLINE = "offline", "Hors ligne"

    device_id = models.CharField("identifiant", max_length=50, unique=True)
    fridge = models.OneToOneField(
        Fridge,
        verbose_name="frigo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device",
    )
    api_key_hash = models.CharField(max_length=128, editable=False)
    last_seen = models.DateTimeField("dernière mesure", null=True, blank=True)
    firmware = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNKNOWN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "nœud IoT"
        verbose_name_plural = "nœuds IoT"
        ordering = ["device_id"]

    def __str__(self):
        return self.device_id

    @staticmethod
    def generate_api_key():
        return secrets.token_urlsafe(32)

    def set_api_key(self, raw_key):
        self.api_key_hash = make_password(raw_key)

    def check_api_key(self, raw_key):
        return bool(raw_key) and check_password(raw_key, self.api_key_hash)

    def rotate_api_key(self):
        """Set a new random key and return it (shown once, never stored in clear)."""
        raw_key = self.generate_api_key()
        self.set_api_key(raw_key)
        return raw_key


class EscalationChain(models.Model):
    """Who is notified for a fridge at each escalation level (N1, N2, N3)."""

    class Level(models.IntegerChoices):
        N1 = 1, "N1 — Responsable frigo"
        N2 = 2, "N2 — Supérieur"
        N3 = 3, "N3 — Administrateur"

    fridge = models.ForeignKey(
        Fridge, verbose_name="frigo", on_delete=models.CASCADE, related_name="escalation"
    )
    level = models.PositiveSmallIntegerField(
        "niveau",
        choices=Level.choices,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        on_delete=models.CASCADE,
        related_name="escalation_entries",
    )

    class Meta:
        verbose_name = "chaîne d'escalade"
        verbose_name_plural = "chaînes d'escalade"
        ordering = ["fridge", "level"]
        constraints = [
            models.UniqueConstraint(
                fields=["fridge", "level", "user"], name="escalation_unique_entry"
            ),
            models.CheckConstraint(
                condition=Q(level__gte=1, level__lte=3), name="escalation_level_1_to_3"
            ),
        ]

    def __str__(self):
        return f"{self.fridge} · N{self.level} · {self.user}"


class Measurement(models.Model):
    """One reading sent by a node. Timestamped by the server on reception."""

    fridge = models.ForeignKey(
        Fridge, verbose_name="frigo", on_delete=models.PROTECT, related_name="measurements"
    )
    device = models.ForeignKey(
        Device,
        verbose_name="nœud",
        on_delete=models.SET_NULL,
        null=True,
        related_name="measurements",
    )
    temperature = models.FloatField("température (°C)", null=True, blank=True)
    humidity = models.FloatField("humidité (%)", null=True, blank=True)
    sensor_ok = models.BooleanField("capteur OK", default=True)
    received_at = models.DateTimeField("reçue le", default=timezone.now)

    class Meta:
        verbose_name = "mesure"
        ordering = ["-received_at"]
        get_latest_by = "received_at"
        indexes = [models.Index(fields=["fridge", "received_at"], name="measure_fridge_time_idx")]

    def __str__(self):
        return f"{self.fridge} · {self.temperature} °C · {self.received_at:%Y-%m-%d %H:%M}"
