import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from incidents.models import Incident
from monitoring.models import Fridge


@pytest.fixture
def fridge(db):
    return Fridge.objects.create(name="Frigo A")


def test_only_one_unfinished_incident_per_fridge(fridge):
    Incident.objects.create(fridge=fridge, type=Incident.Type.TEMPERATURE)
    with pytest.raises(IntegrityError), transaction.atomic():
        Incident.objects.create(fridge=fridge, type=Incident.Type.OFFLINE)


def test_new_incident_allowed_once_previous_ended(fridge):
    Incident.objects.create(fridge=fridge, type=Incident.Type.TEMPERATURE, ended_at=timezone.now())
    Incident.objects.create(fridge=fridge, type=Incident.Type.TEMPERATURE)
    assert fridge.incidents.count() == 2


def test_remaining_minutes_before_compromise(fridge):
    incident = Incident(fridge=fridge, type=Incident.Type.TEMPERATURE, excursion_minutes=90)
    assert incident.remaining_minutes == 10 * 60 - 90
    incident.excursion_minutes = 700
    assert incident.remaining_minutes == 0
