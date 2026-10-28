import pytest
from django.core.management import call_command
from django.db import IntegrityError

from accounts.models import User
from monitoring.models import Device, EscalationChain, Fridge


@pytest.fixture
def fridge(db):
    return Fridge.objects.create(name="Frigo A")


def test_fridge_default_range_is_2_to_8(fridge):
    assert (fridge.temp_min, fridge.temp_max) == (2.0, 8.0)
    assert fridge.max_excursion_hours == 10
    assert fridge.is_temperature_in_range(2.0)
    assert fridge.is_temperature_in_range(8.0)
    assert not fridge.is_temperature_in_range(8.1)
    assert not fridge.is_temperature_in_range(1.9)


def test_humidity_range_is_optional(fridge):
    assert fridge.is_humidity_in_range(99)
    fridge.hum_min, fridge.hum_max = 30, 70
    assert fridge.is_humidity_in_range(50)
    assert not fridge.is_humidity_in_range(75)


@pytest.mark.django_db
def test_fridge_rejects_inverted_range():
    with pytest.raises(IntegrityError):
        Fridge.objects.create(name="Frigo B", temp_min=8, temp_max=2)


def test_device_api_key_is_hashed(fridge):
    device = Device(device_id="FRIGO-A", fridge=fridge)
    raw_key = device.rotate_api_key()
    device.save()
    assert raw_key not in device.api_key_hash
    assert device.check_api_key(raw_key)
    assert not device.check_api_key("wrong-key")
    assert not device.check_api_key("")


def test_escalation_entry_is_unique(fridge):
    user = User.objects.create_user(email="n1@lab.ma", password="x")
    EscalationChain.objects.create(fridge=fridge, level=1, user=user)
    with pytest.raises(IntegrityError):
        EscalationChain.objects.create(fridge=fridge, level=1, user=user)


def test_escalation_level_must_be_1_to_3(fridge):
    user = User.objects.create_user(email="n1@lab.ma", password="x")
    with pytest.raises(IntegrityError):
        EscalationChain.objects.create(fridge=fridge, level=4, user=user)


@pytest.mark.django_db
def test_seed_demo_is_idempotent():
    call_command("seed_demo")
    call_command("seed_demo")
    assert Fridge.objects.count() == 1
    assert Device.objects.count() == 1
    assert EscalationChain.objects.count() == 3


@pytest.fixture
def admin_client(client, db):
    admin = User.objects.create_superuser(email="admin@lab.ma", password="x")
    client.force_login(admin)
    return client


@pytest.mark.parametrize(
    "url",
    [
        "/admin/accounts/user/",
        "/admin/monitoring/fridge/",
        "/admin/monitoring/fridge/add/",
        "/admin/monitoring/device/",
        "/admin/monitoring/escalationchain/",
        "/admin/monitoring/measurement/",
        "/admin/incidents/incident/",
        "/admin/incidents/notification/",
        "/admin/audit/eventlog/",
    ],
)
def test_admin_pages_load(admin_client, url):
    assert admin_client.get(url).status_code == 200


def test_admin_device_creation_shows_key_once(admin_client):
    response = admin_client.post(
        "/admin/monitoring/device/add/", {"device_id": "FRIGO-X"}, follow=True
    )
    device = Device.objects.get(device_id="FRIGO-X")
    shown = [str(m) for m in response.context["messages"] if "Clé API" in str(m)]
    assert len(shown) == 1
    assert device.check_api_key(shown[0].rsplit(" ", 1)[-1])


def test_admin_threshold_change_is_logged(admin_client, fridge):
    from audit.models import EventLog

    response = admin_client.post(
        f"/admin/monitoring/fridge/{fridge.pk}/change/",
        {
            "name": fridge.name,
            "location": "",
            "temp_min": "2.0",
            "temp_max": "7.0",
            "max_excursion_hours": "10",
            "is_active": "on",
            "escalation-TOTAL_FORMS": "0",
            "escalation-INITIAL_FORMS": "0",
        },
    )
    assert response.status_code == 302
    event = EventLog.objects.get(type=EventLog.Type.THRESHOLD_CHANGED)
    assert event.details == {"changes": {"temp_max": [8.0, 7.0]}}
