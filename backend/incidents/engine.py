"""Incident and escalation engine.

Two entry points:

- `on_measurement(measurement)`, called when a node sends a reading: opens an incident
  after N consecutive out-of-range readings (or sensor failures), attaches further
  readings to the unfinished incident, and ends it when a reading is back in range.
- `tick(now)`, run periodically by `manage.py run_alert_engine`: marks silent nodes
  offline, sends notification rounds every NOTIFY_EVERY_MINUTES while an incident is
  not acknowledged, escalates N1 → N1+N2 → N1+N2+N3, raises severity alerts, resumes
  escalation after an acknowledgement that did not fix the problem, and tells the
  recipients when an incident ends.

Notifications are sent by `tick` only, so a slow channel never delays a node's request;
with the default 30 s tick the first alert leaves well under a minute after detection.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from audit.models import EventLog
from audit.services import log_event
from monitoring.models import Device

from . import ack
from .models import Incident, Notification
from .notifiers import NOTIFIERS, Message, channels_for

logger = logging.getLogger(__name__)


def config(key):
    return settings.COLDCHAIN[key]


def minutes_between(start, end):
    return max(0.0, (end - start).total_seconds() / 60)


def format_minutes(minutes):
    hours, mins = divmod(int(round(minutes)), 60)
    if not hours:
        return f"{mins} min"
    return f"{hours} h {mins:02d}"


# --- Measurements ----------------------------------------------------------------------


def out_of_range_type(fridge, measurement):
    """Incident type for a valid reading outside the fridge's ranges, else None."""
    if not fridge.is_temperature_in_range(measurement.temperature):
        return Incident.Type.TEMPERATURE
    if not fridge.is_humidity_in_range(measurement.humidity):
        return Incident.Type.HUMIDITY
    return None


def unfinished_incident(fridge):
    return Incident.objects.filter(fridge=fridge, ended_at__isnull=True).first()


def open_incident(fridge, incident_type, *, started_at, out_since=None):
    try:
        with transaction.atomic():
            incident = Incident.objects.create(
                fridge=fridge, type=incident_type, started_at=started_at, out_since=out_since
            )
    except IntegrityError:
        # Another process opened one in the meantime: there can be only one.
        return unfinished_incident(fridge)
    log_event(EventLog.Type.INCIDENT_OPENED, obj=incident, type=incident_type)
    logger.info("Incident ouvert : %s", incident)
    return incident


def end_incident(incident, now):
    excursion = incident.total_excursion_minutes(now)
    updated = Incident.objects.filter(pk=incident.pk, ended_at__isnull=True).update(
        ended_at=now, status=Incident.Status.ENDED, out_since=None, excursion_minutes=excursion
    )
    if updated:
        incident.refresh_from_db()
        log_event(EventLog.Type.INCIDENT_ENDED, obj=incident, excursion_minutes=round(excursion))
        logger.info("Incident terminé : %s", incident)
    return incident


def last_readings_match(fridge, predicate):
    """True if the last CONSECUTIVE_OUT_OF_RANGE readings all satisfy `predicate`.

    Returns (matched, oldest reading of the series).
    """
    count = max(1, config("CONSECUTIVE_OUT_OF_RANGE"))
    recent = list(fridge.measurements.order_by("-received_at")[:count])
    matched = len(recent) == count and all(predicate(m) for m in recent)
    return matched, (recent[-1] if recent else None)


def on_measurement(measurement):
    """Update incidents after a reading has been stored. Returns the unfinished incident."""
    fridge = measurement.fridge
    if not fridge.is_active:
        return None
    now = measurement.received_at
    device_label = measurement.device.device_id if measurement.device else ""
    incident = unfinished_incident(fridge)

    if not measurement.sensor_ok:
        log_event(EventLog.Type.SENSOR_FAILURE, actor_label=device_label, obj=fridge)
        if incident is None:
            matched, first = last_readings_match(fridge, lambda m: not m.sensor_ok)
            if matched:
                incident = open_incident(fridge, Incident.Type.SENSOR, started_at=first.received_at)
        # An ongoing excursion keeps running: we cannot tell it ended.
        return incident

    out_type = out_of_range_type(fridge, measurement)
    if out_type:
        log_event(
            EventLog.Type.MEASUREMENT_OUT_OF_RANGE,
            actor_label=device_label,
            obj=fridge,
            temperature=measurement.temperature,
            humidity=measurement.humidity,
        )

    if incident is None:
        if out_type is None:
            return None
        matched, first = last_readings_match(
            fridge, lambda m: m.sensor_ok and out_of_range_type(fridge, m) is not None
        )
        if matched:
            incident = open_incident(
                fridge, out_type, started_at=first.received_at, out_since=first.received_at
            )
        return incident

    if out_type is None:
        return end_incident(incident, now)

    # Still (or again) out of range: the reading belongs to the unfinished incident.
    update_fields = []
    if incident.type in (Incident.Type.OFFLINE, Incident.Type.SENSOR):
        # The node is back but the fridge is out of range (e.g. after a power cut).
        incident.type = out_type
        update_fields.append("type")
    if incident.out_since is None:
        # Conservative: count from the previous reading, the last time we knew anything.
        previous = fridge.measurements.filter(received_at__lt=now).order_by("-received_at").first()
        incident.out_since = previous.received_at if previous else now
        update_fields.append("out_since")
    if update_fields:
        incident.save(update_fields=update_fields)
    return incident


# --- Periodic tick ---------------------------------------------------------------------


def tick(now=None):
    now = now or timezone.now()
    detect_offline_devices(now)
    unfinished = Incident.objects.filter(
        ended_at__isnull=True, fridge__is_active=True
    ).select_related("fridge")
    for incident in unfinished:
        try:
            process_incident(incident, now)
        except Exception:
            logger.exception("Échec du traitement de l'incident #%s", incident.pk)
    for incident in Incident.objects.filter(ended_at__isnull=False, end_notified=False):
        try:
            notify_end(incident, now)
        except Exception:
            logger.exception("Échec de la notification de fin de l'incident #%s", incident.pk)


def detect_offline_devices(now):
    """Mark nodes silent for OFFLINE_AFTER_MINUTES offline and open an incident.

    Nodes never seen yet (not installed) are ignored.
    """
    limit = now - timedelta(minutes=config("OFFLINE_AFTER_MINUTES"))
    candidates = (
        Device.objects.filter(fridge__isnull=False, fridge__is_active=True, last_seen__lt=limit)
        .exclude(status=Device.Status.OFFLINE)
        .select_related("fridge")
    )
    for device in candidates:
        # Only if no reading arrived since we looked.
        updated = Device.objects.filter(pk=device.pk, last_seen=device.last_seen).update(
            status=Device.Status.OFFLINE
        )
        if not updated:
            continue
        log_event(
            EventLog.Type.DEVICE_OFFLINE,
            obj=device,
            last_seen=device.last_seen.isoformat(),
        )
        logger.warning("Nœud hors ligne : %s", device)
        if unfinished_incident(device.fridge) is None:
            open_incident(device.fridge, Incident.Type.OFFLINE, started_at=now)


def level_for_round(round_index):
    """Escalation level of the n-th notification round (0-based)."""
    if round_index >= config("ESCALATE_N3_AFTER_ROUNDS"):
        return 3
    if round_index >= config("ESCALATE_N2_AFTER_ROUNDS"):
        return 2
    return 1


def raise_level(incident, level, reason):
    if level <= incident.current_level:
        return
    previous = incident.current_level
    incident.current_level = level
    incident.save(update_fields=["current_level"])
    log_event(
        EventLog.Type.INCIDENT_ESCALATED, obj=incident, level=[previous, level], reason=reason
    )


def process_incident(incident, now):
    fridge = incident.fridge
    excursion = incident.total_excursion_minutes(now)

    # Severity: immediate alert to every level, even if the incident is acknowledged.
    reached = [h for h in config("SEVERITY_HOURS") if excursion >= h * 60]
    if reached and max(reached) > incident.severity_hours_reached:
        hours = max(reached)
        incident.severity_hours_reached = hours
        incident.save(update_fields=["severity_hours_reached"])
        raise_level(incident, 3, reason=f"{hours:g} h hors plage")
        send_round(incident, now, note=f"{hours:g} h hors plage")

    if excursion >= fridge.max_excursion_hours * 60 and not incident.reagents_compromised:
        incident.reagents_compromised = True
        incident.save(update_fields=["reagents_compromised"])
        log_event(
            EventLog.Type.REAGENTS_COMPROMISED, obj=incident, excursion_minutes=round(excursion)
        )
        raise_level(incident, 3, reason="réactifs compromis")
        send_round(incident, now, note="réactifs compromis")

    # Acknowledged but still not fixed: escalation resumes one level higher.
    resume_after = timedelta(minutes=config("RESUME_AFTER_ACK_MINUTES"))
    if (
        incident.status == Incident.Status.ACKNOWLEDGED
        and incident.acked_at
        and now - incident.acked_at >= resume_after
    ):
        updated = Incident.objects.filter(
            pk=incident.pk, status=Incident.Status.ACKNOWLEDGED, ended_at__isnull=True
        ).update(status=Incident.Status.OPEN, acked_by=None, acked_at=None)
        if updated:
            incident.refresh_from_db()
            raise_level(incident, min(incident.current_level + 1, 3), reason="reprise")
            send_round(incident, now, note="toujours non résolu après la prise en charge")
        return

    if incident.status != Incident.Status.OPEN:
        return
    every = timedelta(minutes=config("NOTIFY_EVERY_MINUTES"))
    if incident.last_notified_at is None or now - incident.last_notified_at >= every:
        raise_level(incident, level_for_round(incident.notification_count), reason="escalade")
        send_round(incident, now)


# --- Notifications ---------------------------------------------------------------------


def recipients(fridge, level):
    """Active users of the fridge's chain up to `level`; all admins if there is nobody."""
    users = list(
        User.objects.filter(
            escalation_entries__fridge=fridge, escalation_entries__level__lte=level, is_active=True
        )
        .distinct()
        .order_by("email")
    )
    if not users:
        users = list(User.objects.filter(role=User.Role.ADMIN, is_active=True).order_by("email"))
    return users


def alert_text(incident, now, note=""):
    fridge = incident.fridge
    title = f"{fridge.name} — {incident.get_type_display()}"
    if incident.reagents_compromised:
        title = f"RÉACTIFS COMPROMIS — {title}"
    elif note:
        title = f"URGENT — {title}"

    lines = []
    if note:
        lines.append(f"⚠ {note[0].upper()}{note[1:]}.")
    last = fridge.measurements.order_by("-received_at").first()
    if last is None:
        lines.append("Aucune mesure reçue.")
    elif not last.sensor_ok:
        lines.append(
            f"Dernière lecture invalide (capteur) à {timezone.localtime(last.received_at):%H:%M}."
        )
    else:
        lines.append(
            f"Dernière mesure : {last.temperature:g} °C · {last.humidity:g} % "
            f"à {timezone.localtime(last.received_at):%H:%M}."
        )
    lines.append(f"Plage autorisée : {fridge.temp_min:g}–{fridge.temp_max:g} °C.")
    if incident.type == Incident.Type.OFFLINE:
        lines.append("Le nœud n'envoie plus de mesures (coupure de courant ou de Wi-Fi ?).")
    excursion = incident.total_excursion_minutes(now)
    if excursion:
        remaining = max(0.0, fridge.max_excursion_hours * 60 - excursion)
        lines.append(
            f"Hors plage depuis {format_minutes(excursion)} · reste {format_minutes(remaining)} "
            f"avant le seuil de {fridge.max_excursion_hours} h."
        )
    lines.append(
        f"Incident #{incident.pk} · niveau N{incident.current_level} · "
        f"notification n°{incident.notification_count}."
    )
    return title, "\n".join(lines)


def dispatch(notification, message):
    """Send one notification; never raises."""
    try:
        NOTIFIERS[notification.channel].send(notification, message)
    except Exception as error:
        notification.status = Notification.Status.FAILED
        notification.error = str(error)[:500]
        notification.save(update_fields=["status", "error"])
        log_event(
            EventLog.Type.NOTIFICATION_FAILED,
            obj=notification.incident,
            user=notification.user.email,
            channel=notification.channel,
            error=notification.error,
        )
        logger.warning("Échec d'envoi %s à %s : %s", notification.channel, notification.user, error)
    else:
        notification.status = Notification.Status.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "sent_at"])
        log_event(
            EventLog.Type.NOTIFICATION_SENT,
            obj=notification.incident,
            user=notification.user.email,
            channel=notification.channel,
            level=notification.level,
            kind=notification.kind,
        )


def send_round(incident, now, note=""):
    """Notify every recipient of the incident's current level on all their channels."""
    incident.notification_count += 1
    incident.last_notified_at = now
    incident.save(update_fields=["notification_count", "last_notified_at"])
    title, body = alert_text(incident, now, note)
    urgent = bool(note) or incident.current_level >= 3

    for user in recipients(incident.fridge, incident.current_level):
        for channel in channels_for(user):
            notification = Notification.objects.create(
                incident=incident, user=user, channel=channel, level=incident.current_level
            )
            api_url, page_url = ack.ack_urls(notification)
            dispatch(
                notification,
                Message(title, body, urgent=urgent, ack_api_url=api_url, ack_page_url=page_url),
            )


def notify_end(incident, now):
    """Tell everyone who was alerted that the incident is over (once)."""
    if not Incident.objects.filter(pk=incident.pk, end_notified=False).update(end_notified=True):
        return
    alerted = (
        Notification.objects.filter(incident=incident, kind=Notification.Kind.ALERT)
        .order_by()  # the default ordering would defeat distinct()
        .values_list("user", "channel")
        .distinct()
    )
    if not alerted:
        return
    fridge = incident.fridge
    title = f"{fridge.name} — retour à la normale"
    body = (
        f"L'incident #{incident.pk} ({incident.get_type_display().lower()}) est terminé.\n"
        f"Durée totale hors plage : {format_minutes(incident.excursion_minutes)}.\n"
        "Une clôture avec commentaire par le N2 ou l'administrateur reste à faire."
    )
    users = User.objects.in_bulk({user_id for user_id, _ in alerted})
    for user_id, channel in alerted:
        user = users.get(user_id)
        if user is None or not user.is_active:
            continue
        notification = Notification.objects.create(
            incident=incident,
            user=user,
            channel=channel,
            level=incident.current_level,
            kind=Notification.Kind.RESOLVED,
        )
        dispatch(notification, Message(title, body))
