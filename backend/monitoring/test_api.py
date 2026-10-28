from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from audit.models import EventLog
from incidents.models import Incident
from monitoring.models import Device, Fridge, Measurement

URL = "/api/measurements/"


def payload(**overrides):
    data = {
        "device_id": "FRIGO-A",
        "temperature": 5.2,
        "humidity": 48.0,
        "sensor_ok": True,
        "firmware": "1.0.0",
    }
    data.update(overrides)
    return data


def post_measurement(api, key, **overrides):
    return api().post(URL, payload(**overrides), format="json", HTTP_X_DEVICE_KEY=key)


# --- Ingestion by the node -------------------------------------------------------------


def test_node_posts_measurement(api, device_and_key):
    device, key = device_and_key
    response = post_measurement(api, key)
    assert response.status_code == 201
    m = Measurement.objects.get()
    assert (m.fridge, m.device, m.temperature, m.humidity) == (device.fridge, device, 5.2, 48.0)
    device.refresh_from_db()
    assert device.status == Device.Status.ONLINE
    assert device.firmware == "1.0.0"
    assert device.last_seen == m.received_at


def test_server_sets_timestamp(api, device_and_key):
    _, key = device_and_key
    with freeze_time("2026-10-28 10:00:00"):
        post_measurement(api, key, received_at="2000-01-01T00:00:00Z")
    assert Measurement.objects.get().received_at.year == 2026


@pytest.mark.parametrize("key", ["wrong-key", ""])
def test_invalid_or_missing_key_is_rejected(api, device_and_key, key):
    response = post_measurement(api, key)
    assert response.status_code == 401
    assert not Measurement.objects.exists()


def test_rejected_key_is_logged(api, device_and_key):
    post_measurement(api, "wrong-key")
    event = EventLog.objects.get(type=EventLog.Type.DEVICE_KEY_REJECTED)
    assert event.actor_label == "FRIGO-A"


def test_key_of_another_device_is_rejected(api, device_and_key, other_fridge):
    other = Device(device_id="FRIGO-B", fridge=other_fridge)
    other_key = other.rotate_api_key()
    other.save()
    assert post_measurement(api, other_key).status_code == 401


def test_logged_in_user_cannot_post_measurement(api, n1, device_and_key):
    response = api(n1).post(URL, payload(), format="json")
    assert response.status_code == 403


def test_sensor_failure_is_recorded(api, device_and_key):
    _, key = device_and_key
    response = post_measurement(api, key, temperature=None, humidity=None, sensor_ok=False)
    assert response.status_code == 201
    m = Measurement.objects.get()
    assert m.sensor_ok is False and m.temperature is None


def test_missing_values_with_sensor_ok_is_invalid(api, device_and_key):
    _, key = device_and_key
    assert post_measurement(api, key, temperature=None).status_code == 400


def test_unattached_device_is_rejected(api, db):
    device = Device(device_id="FRIGO-A")
    key = device.rotate_api_key()
    device.save()
    assert post_measurement(api, key).status_code == 409


def test_device_back_online_is_logged(api, device_and_key):
    device, key = device_and_key
    device.status = Device.Status.OFFLINE
    device.save()
    post_measurement(api, key)
    assert EventLog.objects.filter(type=EventLog.Type.DEVICE_ONLINE).count() == 1


# --- Fridges and dashboard -------------------------------------------------------------


def test_fridges_are_scoped_to_escalation_chain(
    api, n1, admin_user, outsider, fridge, other_fridge
):
    def names(user):
        return [f["name"] for f in api(user).get("/api/fridges/").data["results"]]

    assert names(n1) == ["Frigo A"]
    assert names(admin_user) == ["Frigo A", "Frigo B"]
    assert names(outsider) == []
    assert api(n1).get(f"/api/fridges/{other_fridge.pk}/").status_code == 404


def test_dashboard_card(api, n1, device_and_key):
    device, key = device_and_key
    post_measurement(api, key, temperature=4.0, humidity=50.0)
    card = api(n1).get(f"/api/fridges/{device.fridge.pk}/").data
    assert card["status"] == "normal"
    assert card["last_measurement"]["temperature"] == 4.0
    assert card["device"]["device_id"] == "FRIGO-A"
    assert card["open_incident"] is None


def test_status_offline_without_recent_measurement(api, n1, device_and_key):
    device, key = device_and_key
    with freeze_time(timezone.now() - timedelta(hours=1)):
        post_measurement(api, key)
    assert api(n1).get(f"/api/fridges/{device.fridge.pk}/").data["status"] == "offline"


def test_status_alert_with_open_incident(api, n1, device_and_key):
    device, key = device_and_key
    post_measurement(api, key, temperature=12.0)
    Incident.objects.create(fridge=device.fridge, type=Incident.Type.TEMPERATURE)
    card = api(n1).get(f"/api/fridges/{device.fridge.pk}/").data
    assert card["status"] == "alert"
    assert card["open_incident"]["remaining_minutes"] == 600


def test_only_admin_manages_fridges(api, n1, admin_user, fridge):
    assert api(n1).post("/api/fridges/", {"name": "X"}).status_code == 403
    assert api(n1).patch(f"/api/fridges/{fridge.pk}/", {"name": "Y"}).status_code == 403
    response = api(admin_user).post("/api/fridges/", {"name": "Frigo C", "location": "Salle 2"})
    assert response.status_code == 201
    assert response.data["temp_min"] == 2.0 and response.data["status"] == "offline"
    assert EventLog.objects.filter(type=EventLog.Type.OBJECT_CREATED).exists()


def test_fridge_with_history_cannot_be_deleted(api, admin_user, device_and_key):
    device, key = device_and_key
    post_measurement(api, key)
    response = api(admin_user).delete(f"/api/fridges/{device.fridge.pk}/")
    assert response.status_code == 409
    assert Fridge.objects.filter(pk=device.fridge.pk).exists()
    assert not EventLog.objects.filter(type=EventLog.Type.OBJECT_DELETED).exists()


# --- Thresholds ------------------------------------------------------------------------


def test_admin_changes_thresholds_and_it_is_logged(api, admin_user, fridge):
    url = f"/api/fridges/{fridge.pk}/thresholds/"
    response = api(admin_user).patch(url, {"temp_max": 7.0}, format="json")
    assert response.status_code == 200
    assert response.data["temp_max"] == 7.0
    event = EventLog.objects.get(type=EventLog.Type.THRESHOLD_CHANGED)
    assert event.details == {"changes": {"temp_max": [8.0, 7.0]}}
    assert event.actor == admin_user


def test_fridge_update_also_logs_threshold_change(api, admin_user, fridge):
    api(admin_user).patch(f"/api/fridges/{fridge.pk}/", {"temp_min": 1.0}, format="json")
    assert EventLog.objects.filter(type=EventLog.Type.THRESHOLD_CHANGED).count() == 1


def test_inverted_thresholds_rejected(api, admin_user, fridge):
    url = f"/api/fridges/{fridge.pk}/thresholds/"
    response = api(admin_user).patch(url, {"temp_min": 9.0}, format="json")
    assert response.status_code == 400
    assert "temp_max" in response.data


def test_n1_cannot_change_thresholds(api, n1, fridge):
    url = f"/api/fridges/{fridge.pk}/thresholds/"
    assert api(n1).patch(url, {"temp_max": 7.0}, format="json").status_code == 403


# --- Series, history, export -----------------------------------------------------------


@pytest.fixture
def history(fridge, device_and_key):
    device, _ = device_and_key
    now = timezone.now()
    for hours_ago, temp in [(48, 3.0), (12, 4.0), (1, 5.0)]:
        Measurement.objects.create(
            fridge=fridge,
            device=device,
            temperature=temp,
            humidity=50.0,
            received_at=now - timedelta(hours=hours_ago),
        )
    return fridge


def test_series_defaults_to_last_24h(api, n1, history):
    data = api(n1).get(f"/api/fridges/{history.pk}/measurements/").data
    assert [m["temperature"] for m in data["results"]] == [4.0, 5.0]


def test_series_custom_range(api, n1, history):
    start = (timezone.now() - timedelta(days=3)).date().isoformat()
    data = api(n1).get(f"/api/fridges/{history.pk}/measurements/?from={start}").data
    assert data["count"] == 3


def test_series_bad_date(api, n1, history):
    url = f"/api/fridges/{history.pk}/measurements/?from=hier"
    assert api(n1).get(url).status_code == 400


def test_history_is_paginated_and_scoped(api, n1, outsider, history):
    data = api(n1).get(f"{URL}?fridge={history.pk}&page_size=2").data
    assert data["count"] == 3 and len(data["results"]) == 2
    assert data["results"][0]["fridge_name"] == "Frigo A"
    assert api(outsider).get(URL).data["count"] == 0


def test_csv_export(api, n1, history):
    start = (timezone.now() - timedelta(days=3)).date().isoformat()
    response = api(n1).get(f"/api/fridges/{history.pk}/measurements/export/?from={start}")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    lines = response.content.decode("utf-8-sig").strip().splitlines()
    assert lines[0] == "date;temperature_c;humidite_pct;capteur_ok"
    assert len(lines) == 4
    assert lines[1].endswith(";3,0;50,0;oui")


# --- Devices and escalation (admin) ----------------------------------------------------


def test_device_created_with_key_shown_once(api, admin_user, fridge):
    response = api(admin_user).post(
        "/api/devices/", {"device_id": "FRIGO-A", "fridge": fridge.pk}, format="json"
    )
    assert response.status_code == 201
    key = response.data["api_key"]
    assert "api_key" not in api(admin_user).get(f"/api/devices/{response.data['id']}/").data
    assert post_measurement(api, key).status_code == 201


def test_device_key_rotation(api, admin_user, device_and_key):
    device, old_key = device_and_key
    response = api(admin_user).post(f"/api/devices/{device.pk}/rotate-key/")
    new_key = response.data["api_key"]
    assert post_measurement(api, old_key).status_code == 401
    assert post_measurement(api, new_key).status_code == 201


def test_one_device_per_fridge(api, admin_user, device_and_key):
    device, _ = device_and_key
    response = api(admin_user).post(
        "/api/devices/", {"device_id": "FRIGO-A2", "fridge": device.fridge.pk}, format="json"
    )
    assert response.status_code == 400


def test_admin_endpoints_forbidden_to_n1(api, n1):
    for url in ["/api/devices/", "/api/escalation/", "/api/users/", "/api/events/"]:
        assert api(n1).get(url).status_code == 403, url


def test_escalation_chain_management(api, admin_user, fridge, outsider):
    response = api(admin_user).post(
        "/api/escalation/", {"fridge": fridge.pk, "level": 3, "user": outsider.pk}, format="json"
    )
    assert response.status_code == 201
    # The new member now sees the fridge.
    assert api(outsider).get("/api/fridges/").data["count"] == 1
    duplicate = api(admin_user).post(
        "/api/escalation/", {"fridge": fridge.pk, "level": 3, "user": outsider.pk}, format="json"
    )
    assert duplicate.status_code == 400
