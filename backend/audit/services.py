from .models import EventLog


def log_event(event_type, *, actor=None, actor_label="", obj=None, **details):
    """Append an entry to the audit trail.

    `actor` is a user (or None for the system); `actor_label` overrides the
    displayed actor, e.g. a device id. Extra keyword arguments go to `details`
    and must be JSON-serializable.
    """
    if not actor_label:
        actor_label = str(actor) if actor is not None else "système"
    return EventLog.objects.create(
        type=event_type,
        actor=actor,
        actor_label=actor_label,
        object_type=obj._meta.model_name if obj is not None else "",
        object_id=str(obj.pk) if obj is not None else "",
        object_repr=str(obj)[:200] if obj is not None else "",
        details=details,
    )
