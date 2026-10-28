from audit.models import EventLog
from audit.services import log_event


def test_admin_reads_event_log(api, admin_user, fridge):
    log_event(EventLog.Type.THRESHOLD_CHANGED, actor=admin_user, obj=fridge)
    log_event(EventLog.Type.DEVICE_OFFLINE)
    data = api(admin_user).get("/api/events/?type=threshold_changed").data
    assert data["count"] == 1
    assert data["results"][0]["type_label"] == "Seuil modifié"
    assert data["results"][0]["object_repr"] == "Frigo A"


def test_event_log_is_read_only_through_api(api, admin_user):
    event = log_event(EventLog.Type.USER_LOGIN)
    client = api(admin_user)
    assert client.delete(f"/api/events/{event.pk}/").status_code == 405
    assert client.post("/api/events/", {}).status_code == 405
