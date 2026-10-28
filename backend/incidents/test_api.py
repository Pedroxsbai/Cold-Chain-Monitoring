import pytest
from django.utils import timezone

from audit.models import EventLog
from incidents.models import Incident


@pytest.fixture
def incident(fridge):
    return Incident.objects.create(fridge=fridge, type=Incident.Type.TEMPERATURE)


@pytest.fixture
def ended_incident(fridge):
    return Incident.objects.create(
        fridge=fridge,
        type=Incident.Type.TEMPERATURE,
        status=Incident.Status.ENDED,
        ended_at=timezone.now(),
    )


def url(incident, action=""):
    return f"/api/incidents/{incident.pk}/{action + '/' if action else ''}"


def test_incidents_are_scoped(api, n1, outsider, admin_user, incident):
    assert api(n1).get("/api/incidents/").data["count"] == 1
    assert api(admin_user).get("/api/incidents/").data["count"] == 1
    assert api(outsider).get("/api/incidents/").data["count"] == 0
    assert api(outsider).post(url(incident, "ack")).status_code == 404


def test_active_filter(api, n1, ended_incident):
    assert api(n1).get("/api/incidents/?active=true").data["count"] == 0
    assert api(n1).get("/api/incidents/").data["count"] == 1


def test_n1_acknowledges(api, n1, incident):
    data = api(n1).get(url(incident)).data
    assert data["can_ack"] is True and data["can_close"] is False

    response = api(n1).post(url(incident, "ack"))
    assert response.status_code == 200
    assert response.data["status"] == "acknowledged"
    assert response.data["acked_by_name"] == "Nadia"
    event = EventLog.objects.get(type=EventLog.Type.INCIDENT_ACKED)
    assert event.actor == n1 and event.details == {"via": "app"}


def test_second_ack_conflicts(api, n1, n2, incident):
    api(n1).post(url(incident, "ack"))
    assert api(n2).post(url(incident, "ack")).status_code == 409
    incident.refresh_from_db()
    assert incident.acked_by == n1


def test_comment(api, n1, incident):
    response = api(n1).post(url(incident, "comments"), {"text": "Porte refermée."})
    assert response.status_code == 201
    detail = api(n1).get(url(incident)).data
    assert [c["text"] for c in detail["comments"]] == ["Porte refermée."]


def test_n1_cannot_close(api, n1, ended_incident):
    response = api(n1).post(url(ended_incident, "close"), {"comment": "OK"})
    assert response.status_code == 403


def test_n2_closes_ended_incident(api, n2, ended_incident):
    assert api(n2).get(url(ended_incident)).data["can_close"] is True
    response = api(n2).post(url(ended_incident, "close"), {"comment": "Réactifs vérifiés."})
    assert response.status_code == 200
    assert response.data["status"] == "closed"
    assert response.data["closing_comment"] == "Réactifs vérifiés."
    assert EventLog.objects.filter(type=EventLog.Type.INCIDENT_CLOSED).count() == 1


def test_admin_closes_without_being_in_chain(api, admin_user, ended_incident):
    response = api(admin_user).post(url(ended_incident, "close"), {"comment": "Clôture admin"})
    assert response.status_code == 200


def test_close_requires_comment(api, n2, ended_incident):
    assert api(n2).post(url(ended_incident, "close"), {"comment": "  "}).status_code == 400


def test_cannot_close_ongoing_incident(api, n2, incident):
    assert api(n2).post(url(incident, "close"), {"comment": "trop tôt"}).status_code == 409
