"""Incident engine and escalation rules (cahier des charges §7)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command
from freezegun import freeze_time

from audit.models import EventLog
from incidents import engine
from incidents.models import Incident, Notification
from monitoring.models import Device, EscalationChain
from monitoring.services import record_measurement

T0 = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


@pytest.fixture
def n3(make_user):
    return make_user("n3@lab.ma")


@pytest.fixture
def chain(fridge, n3):
    """Frigo A with N1 (n1), N2 (n2) and N3 (n3)."""
    EscalationChain.objects.create(fridge=fridge, level=3, user=n3)
    return fridge


@pytest.fixture
def device(device_and_key, chain):
    return device_and_key[0]


def measure(device, minutes, temperature=5.0, humidity=50.0, sensor_ok=True):
    with freeze_time(at(minutes)):
        record_measurement(device, temperature=temperature, humidity=humidity, sensor_ok=sensor_ok)
    device.refresh_from_db()


def tick(minutes):
    engine.tick(at(minutes))


def incident():
    return Incident.objects.get()


def recipients_of_round(round_number):
    """E-mails notified in the n-th round (1-based), from the alert notifications."""
    alerts = Notification.objects.filter(kind=Notification.Kind.ALERT, channel="email")
    rounds = []
    # Rounds are created in order and N1 is in every round: a repeated user starts a new one.
    for notification in alerts.order_by("id"):
        if not rounds or notification.user.email in rounds[-1]:
            rounds.append([])
        rounds[-1].append(notification.user.email)
    return sorted(rounds[round_number - 1])


# --- Opening, attaching, ending --------------------------------------------------------


def test_one_reading_out_of_range_does_not_open(device):
    measure(device, 0, temperature=12)
    assert not Incident.objects.exists()
    assert EventLog.objects.filter(type=EventLog.Type.MEASUREMENT_OUT_OF_RANGE).count() == 1


def test_two_consecutive_readings_open_incident(device):
    measure(device, 0, temperature=12)
    measure(device, 20, temperature=12.5)
    inc = incident()
    assert inc.type == Incident.Type.TEMPERATURE
    assert inc.status == Incident.Status.OPEN
    # Counted from the first out-of-range reading.
    assert inc.started_at == at(0) and inc.out_since == at(0)
    assert EventLog.objects.filter(type=EventLog.Type.INCIDENT_OPENED).count() == 1


def test_reading_back_in_range_between_resets_the_count(device):
    measure(device, 0, temperature=12)
    measure(device, 20, temperature=5)
    measure(device, 40, temperature=12)
    assert not Incident.objects.exists()


def test_single_reading_opens_when_configured(device, settings):
    settings.COLDCHAIN = {**settings.COLDCHAIN, "CONSECUTIVE_OUT_OF_RANGE": 1}
    measure(device, 0, temperature=-1)
    assert incident().type == Incident.Type.TEMPERATURE


def test_following_readings_attach_to_the_same_incident(device):
    for minutes in (0, 20, 40, 60):
        measure(device, minutes, temperature=12)
    assert Incident.objects.count() == 1


def test_back_in_range_ends_incident_with_excursion(device):
    measure(device, 0, temperature=12)
    measure(device, 20, temperature=12)
    measure(device, 90, temperature=5)
    inc = incident()
    assert inc.status == Incident.Status.ENDED
    assert inc.ended_at == at(90)
    assert inc.excursion_minutes == 90
    assert inc.out_since is None
    assert EventLog.objects.filter(type=EventLog.Type.INCIDENT_ENDED).count() == 1


def test_live_excursion_and_countdown(device):
    measure(device, 0, temperature=12)
    measure(device, 20, temperature=12)
    inc = incident()
    assert inc.total_excursion_minutes(at(150)) == 150
    with freeze_time(at(150)):
        assert inc.remaining_minutes == 600 - 150


def test_humidity_incident(device, fridge):
    fridge.hum_min, fridge.hum_max = 30, 70
    fridge.save()
    measure(device, 0, humidity=85)
    measure(device, 20, humidity=90)
    assert incident().type == Incident.Type.HUMIDITY


def test_sensor_failures_open_sensor_incident(device):
    measure(device, 0, temperature=None, humidity=None, sensor_ok=False)
    assert not Incident.objects.exists()
    measure(device, 20, temperature=None, humidity=None, sensor_ok=False)
    assert incident().type == Incident.Type.SENSOR
    measure(device, 40, temperature=5)
    assert incident().status == Incident.Status.ENDED


def test_sensor_failure_does_not_end_an_excursion(device):
    measure(device, 0, temperature=12)
    measure(device, 20, temperature=12)
    measure(device, 40, temperature=None, humidity=None, sensor_ok=False)
    inc = incident()
    assert inc.ended_at is None and inc.out_since == at(0)


def test_inactive_fridge_is_ignored(device, fridge):
    fridge.is_active = False
    fridge.save()
    measure(device, 0, temperature=12)
    measure(device, 20, temperature=12)
    assert not Incident.objects.exists()


# --- Offline nodes ---------------------------------------------------------------------


def test_silent_node_goes_offline_and_opens_incident(device):
    measure(device, 0)
    tick(45)  # exactly 45 min: not yet
    assert not Incident.objects.exists()
    tick(46)
    device.refresh_from_db()
    assert device.status == Device.Status.OFFLINE
    assert incident().type == Incident.Type.OFFLINE
    assert EventLog.objects.filter(type=EventLog.Type.DEVICE_OFFLINE).count() == 1
    tick(70)  # no duplicate
    assert EventLog.objects.filter(type=EventLog.Type.DEVICE_OFFLINE).count() == 1


def test_node_back_in_range_ends_offline_incident(device):
    measure(device, 0)
    tick(50)
    measure(device, 80)
    assert device.status == Device.Status.ONLINE
    assert incident().status == Incident.Status.ENDED


def test_node_back_out_of_range_turns_offline_into_temperature(device):
    measure(device, 0)
    tick(50)
    measure(device, 120, temperature=14)
    inc = incident()
    assert inc.type == Incident.Type.TEMPERATURE
    assert inc.ended_at is None
    # Conservative: counted from the last reading before the outage.
    assert inc.out_since == at(0)


def test_never_seen_node_is_not_reported_offline(device):
    tick(600)
    assert not Incident.objects.exists()


# --- Escalation ------------------------------------------------------------------------


@pytest.fixture
def open_incident(device):
    measure(device, 0, temperature=12)
    measure(device, 0.5, temperature=12)
    return incident()


def test_first_round_goes_to_n1_right_away(open_incident, mailoutbox):
    tick(1)
    inc = incident()
    assert inc.notification_count == 1 and inc.current_level == 1
    assert [m.to for m in mailoutbox] == [["n1@lab.ma"]]
    assert "Frigo A" in mailoutbox[0].subject
    assert "12 °C" in mailoutbox[0].body
    assert "/ack/" in mailoutbox[0].body


def test_no_new_round_before_20_minutes(open_incident):
    tick(1)
    tick(20)
    assert incident().notification_count == 1
    tick(21)
    assert incident().notification_count == 2


def test_escalation_after_4_then_8_rounds(open_incident):
    for i in range(10):
        tick(1 + 20 * i)
    assert recipients_of_round(1) == ["n1@lab.ma"]
    assert recipients_of_round(4) == ["n1@lab.ma"]
    assert recipients_of_round(5) == ["n1@lab.ma", "n2@lab.ma"]
    assert recipients_of_round(8) == ["n1@lab.ma", "n2@lab.ma"]
    assert recipients_of_round(9) == ["n1@lab.ma", "n2@lab.ma", "n3@lab.ma"]
    assert incident().current_level == 3
    escalations = EventLog.objects.filter(type=EventLog.Type.INCIDENT_ESCALATED)
    assert [e.details["level"] for e in escalations.order_by("timestamp")] == [[1, 2], [2, 3]]


def test_acknowledgement_stops_rounds(open_incident, n1):
    from incidents.services import acknowledge

    tick(1)
    with freeze_time(at(5)):
        acknowledge(incident(), n1)
    tick(30)
    tick(60)
    assert incident().notification_count == 1


def test_escalation_resumes_2h_after_ack_if_not_fixed(open_incident, n1, mailoutbox):
    from incidents.services import acknowledge

    tick(1)
    with freeze_time(at(5)):
        acknowledge(incident(), n1)
    tick(124)
    assert incident().status == Incident.Status.ACKNOWLEDGED
    mailoutbox.clear()
    tick(126)
    inc = incident()
    assert inc.status == Incident.Status.OPEN
    assert inc.acked_by is None
    assert inc.current_level == 2
    assert sorted(m.to[0] for m in mailoutbox) == ["n1@lab.ma", "n2@lab.ma"]


def test_severity_5h_alerts_all_levels_even_if_acknowledged(open_incident, n1, mailoutbox):
    from incidents.services import acknowledge

    tick(1)
    inc = incident()
    with freeze_time(at(5)):
        acknowledge(inc, n1)
    # Keep the acknowledgement fresh so only the severity rule can notify.
    Incident.objects.filter(pk=inc.pk).update(acked_at=at(290))
    mailoutbox.clear()
    tick(301)
    inc = incident()
    assert inc.severity_hours_reached == 5
    assert inc.current_level == 3
    assert sorted(m.to[0] for m in mailoutbox) == ["n1@lab.ma", "n2@lab.ma", "n3@lab.ma"]
    assert all(m.subject.startswith("[Cold Chain] URGENT") for m in mailoutbox)
    tick(302)  # sent once per threshold
    assert incident().severity_hours_reached == 5
    assert len(mailoutbox) == 3


def test_reagents_compromised_after_10h(open_incident):
    tick(1)
    tick(601)
    inc = incident()
    assert inc.reagents_compromised
    assert EventLog.objects.filter(type=EventLog.Type.REAGENTS_COMPROMISED).count() == 1
    assert Notification.objects.filter(incident=inc, sent_at__isnull=False).exists()


def test_end_of_incident_is_notified_once(open_incident, device, mailoutbox):
    tick(1)
    tick(22)  # two alert rounds to the same person
    measure(device, 30, temperature=5)
    mailoutbox.clear()
    tick(31)
    tick(32)
    assert [m.to for m in mailoutbox] == [["n1@lab.ma"]]
    assert "retour à la normale" in mailoutbox[0].subject
    assert incident().end_notified


def test_empty_chain_falls_back_to_admins(db, admin_user, mailoutbox):
    from monitoring.models import Fridge

    fridge = Fridge.objects.create(name="Frigo orphelin")
    device = Device(device_id="ORPHAN", fridge=fridge)
    device.rotate_api_key()
    device.save()
    measure(device, 0, temperature=12)
    measure(device, 1, temperature=12)
    tick(2)
    assert [m.to for m in mailoutbox] == [["admin@lab.ma"]]


# --- Channels --------------------------------------------------------------------------


def test_ntfy_notification_has_ack_button(open_incident, n1, ntfy):
    n1.ntfy_topic = "labo-n1"
    n1.save()
    tick(1)
    assert len(ntfy.calls) == 1
    payload = ntfy.calls[0]["json"]
    assert payload["topic"] == "labo-n1"
    assert payload["priority"] == 4
    action = payload["actions"][0]
    assert action["label"] == "Je prends en charge"
    assert action["method"] == "POST"
    assert "/api/ack/" in action["url"]
    assert set(Notification.objects.values_list("channel", flat=True)) == {"ntfy", "email"}


def test_failed_channel_is_recorded_and_others_still_sent(open_incident, n1, ntfy, mailoutbox):
    n1.ntfy_topic = "labo-n1"
    n1.save()
    ntfy.fail = True
    tick(1)
    failed = Notification.objects.get(channel="ntfy")
    assert failed.status == Notification.Status.FAILED
    assert "injoignable" in failed.error
    assert Notification.objects.get(channel="email").status == Notification.Status.SENT
    assert len(mailoutbox) == 1
    assert EventLog.objects.filter(type=EventLog.Type.NOTIFICATION_FAILED).count() == 1


# --- Acknowledgement links -------------------------------------------------------------


@pytest.fixture
def ack_link(open_incident):
    tick(1)
    notification = Notification.objects.get()
    from incidents.ack import make_token

    with freeze_time(at(1)):  # the token is timestamped
        token = make_token(notification)
    return notification, f"/api/ack/{token}/"


def test_opening_the_link_is_recorded_but_does_not_ack(api, ack_link):
    notification, url = ack_link
    response = api().get(url)
    assert response.status_code == 200
    assert response.data["can_ack"] is True
    assert response.data["incident"]["fridge_name"] == "Frigo A"
    notification.refresh_from_db()
    assert notification.read_at is not None
    assert incident().status == Incident.Status.OPEN
    assert EventLog.objects.filter(type=EventLog.Type.NOTIFICATION_READ).count() == 1


def test_link_acknowledges_once(api, ack_link, n1):
    _, url = ack_link
    response = api().post(url)
    assert response.status_code == 200
    inc = incident()
    assert inc.status == Incident.Status.ACKNOWLEDGED and inc.acked_by == n1
    assert EventLog.objects.get(type=EventLog.Type.INCIDENT_ACKED).details == {"via": "email"}
    assert api().post(url).status_code == 409


def test_link_after_ack_by_someone_else(api, ack_link, n2):
    from incidents.services import acknowledge

    _, url = ack_link
    acknowledge(incident(), n2)
    assert api().get(url).data["can_ack"] is False
    assert api().post(url).status_code == 409


@pytest.mark.parametrize("token", ["garbage", "1:abc:def"])
def test_invalid_link(api, db, token):
    assert api().post(f"/api/ack/{token}/").status_code == 400


def test_expired_link(api, ack_link):
    _, url = ack_link
    with freeze_time(at(1 + 60 * 23)):
        assert api().get(url).status_code == 200
    with freeze_time(at(1 + 60 * 25)):
        assert api().post(url).status_code == 400


# --- Command ---------------------------------------------------------------------------


def test_run_alert_engine_once(open_incident, mailoutbox):
    with freeze_time(at(1)):
        call_command("run_alert_engine", "--once")
    assert incident().notification_count == 1
    assert len(mailoutbox) == 1
