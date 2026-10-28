import pytest

from accounts.models import User
from audit.models import EventLog
from audit.services import log_event
from monitoring.models import Fridge


@pytest.mark.django_db
def test_log_event_records_actor_object_and_details():
    user = User.objects.create_user(email="admin@lab.ma", password="x", first_name="Ali")
    fridge = Fridge.objects.create(name="Frigo A")
    event = log_event(EventLog.Type.THRESHOLD_CHANGED, actor=user, obj=fridge, temp_max=[8, 7])
    assert event.actor_label == "Ali"
    assert (event.object_type, event.object_id, event.object_repr) == (
        "fridge",
        str(fridge.pk),
        "Frigo A",
    )
    assert event.details == {"temp_max": [8, 7]}


@pytest.mark.django_db
def test_system_event_without_actor():
    event = log_event(EventLog.Type.DEVICE_OFFLINE)
    assert event.actor is None
    assert event.actor_label == "système"


@pytest.mark.django_db
def test_event_log_is_append_only():
    event = log_event(EventLog.Type.USER_LOGIN)
    event.actor_label = "tampered"
    with pytest.raises(PermissionError):
        event.save()
    with pytest.raises(PermissionError):
        event.delete()
    with pytest.raises(PermissionError):
        EventLog.objects.all().update(actor_label="tampered")
    with pytest.raises(PermissionError):
        EventLog.objects.all().delete()
