from django.db.models import Max
from django.utils import timezone

from audit.models import EventLog
from audit.services import log_event
from monitoring.models import EscalationChain

from .models import Incident, IncidentComment


class IncidentActionError(Exception):
    """An action that is not allowed in the incident's current state."""


def user_levels(user):
    """Map fridge id → highest escalation level of `user` on that fridge."""
    rows = (
        EscalationChain.objects.filter(user=user)
        .values("fridge")
        .annotate(level=Max("level"))
        .values_list("fridge", "level")
    )
    return dict(rows)


def can_acknowledge(incident):
    return incident.status == Incident.Status.OPEN


def can_close(user, incident, level):
    """Closing needs an ended incident and N2+ on the fridge (or admin)."""
    if incident.status != Incident.Status.ENDED:
        return False
    return user.is_admin or (level or 0) >= 2


def acknowledge(incident, user, *, via="app"):
    """Take charge of an open incident. Only one user can win if two click at once."""
    now = timezone.now()
    updated = Incident.objects.filter(pk=incident.pk, status=Incident.Status.OPEN).update(
        status=Incident.Status.ACKNOWLEDGED, acked_by=user, acked_at=now
    )
    if not updated:
        raise IncidentActionError("Cet incident n'est plus en attente de prise en charge.")
    incident.refresh_from_db()
    log_event(EventLog.Type.INCIDENT_ACKED, actor=user, obj=incident, via=via)
    return incident


def add_comment(incident, user, text):
    comment = IncidentComment.objects.create(incident=incident, author=user, text=text)
    log_event(EventLog.Type.INCIDENT_COMMENTED, actor=user, obj=incident, comment_id=comment.id)
    return comment


def close(incident, user, comment):
    if incident.status != Incident.Status.ENDED:
        raise IncidentActionError(
            "Seul un incident terminé (frigo revenu dans la plage) peut être clôturé."
        )
    incident.status = Incident.Status.CLOSED
    incident.closed_by = user
    incident.closed_at = timezone.now()
    incident.closing_comment = comment
    incident.save(update_fields=["status", "closed_by", "closed_at", "closing_comment"])
    log_event(EventLog.Type.INCIDENT_CLOSED, actor=user, obj=incident)
    return incident
