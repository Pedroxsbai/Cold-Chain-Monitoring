from datetime import timedelta

from django.conf import settings
from django.db.models import OuterRef, Prefetch, Subquery
from django.utils import timezone

from audit.models import EventLog
from audit.services import log_event
from incidents.models import Incident

from .models import Device, Fridge, Measurement

THRESHOLD_FIELDS = ("temp_min", "temp_max", "hum_min", "hum_max", "max_excursion_hours")


class FridgeStatus:
    NORMAL = "normal"
    ALERT = "alert"
    OFFLINE = "offline"


def fridges_for(user):
    """Fridges visible to a user: all for an admin, else those of their escalation chains."""
    if user.is_admin:
        return Fridge.objects.all()
    return Fridge.objects.filter(escalation__user=user).distinct()


def with_dashboard_data(queryset):
    """Annotate fridges with their latest measurement and unfinished incident."""
    latest = Measurement.objects.filter(fridge=OuterRef("pk")).order_by("-received_at")
    return (
        queryset.select_related("device")
        .annotate(
            last_temperature=Subquery(latest.values("temperature")[:1]),
            last_humidity=Subquery(latest.values("humidity")[:1]),
            last_sensor_ok=Subquery(latest.values("sensor_ok")[:1]),
            last_measurement_at=Subquery(latest.values("received_at")[:1]),
        )
        .prefetch_related(
            Prefetch(
                "incidents",
                queryset=Incident.objects.filter(ended_at__isnull=True),
                to_attr="unfinished_incidents",
            )
        )
    )


def fridge_status(*, last_measurement_at, unfinished_incident, device, now=None):
    if unfinished_incident is not None:
        if unfinished_incident.type == Incident.Type.OFFLINE:
            return FridgeStatus.OFFLINE
        return FridgeStatus.ALERT
    now = now or timezone.now()
    offline_after = timedelta(minutes=settings.COLDCHAIN["OFFLINE_AFTER_MINUTES"])
    if device is None or device.status == Device.Status.OFFLINE:
        return FridgeStatus.OFFLINE
    if last_measurement_at is None or now - last_measurement_at > offline_after:
        return FridgeStatus.OFFLINE
    return FridgeStatus.NORMAL


def threshold_snapshot(fridge):
    return {field: getattr(fridge, field) for field in THRESHOLD_FIELDS}


def log_threshold_changes(before, fridge, actor):
    """Log the thresholds that differ between `before` (a snapshot) and `fridge`."""
    changes = {
        field: [before[field], getattr(fridge, field)]
        for field in THRESHOLD_FIELDS
        if before[field] != getattr(fridge, field)
    }
    if changes:
        log_event(EventLog.Type.THRESHOLD_CHANGED, actor=actor, obj=fridge, changes=changes)
    return changes


def record_measurement(device, *, temperature, humidity, sensor_ok, firmware=""):
    """Store a reading received from a node and refresh the node's state."""
    now = timezone.now()
    measurement = Measurement.objects.create(
        fridge=device.fridge,
        device=device,
        temperature=temperature,
        humidity=humidity,
        sensor_ok=sensor_ok,
        received_at=now,
    )

    was_offline = device.status == Device.Status.OFFLINE
    device.last_seen = now
    device.status = Device.Status.ONLINE
    update_fields = ["last_seen", "status"]
    if firmware and firmware != device.firmware:
        device.firmware = firmware
        update_fields.append("firmware")
    device.save(update_fields=update_fields)
    if was_offline:
        log_event(EventLog.Type.DEVICE_ONLINE, actor_label=device.device_id, obj=device)

    return measurement
