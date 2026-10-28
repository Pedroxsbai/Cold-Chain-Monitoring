import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.models import User
from monitoring.models import Device, EscalationChain, Fridge


@pytest.fixture(autouse=True)
def _fast_and_isolated(settings):
    # Real hashers are deliberately slow; tests don't need that.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # Throttle counters live in the cache: reset them between tests.
    cache.clear()


@pytest.fixture
def make_user(db):
    def make(email, role=User.Role.RESPONSIBLE, **extra):
        return User.objects.create_user(email=email, password="S3cret-pass!", role=role, **extra)

    return make


@pytest.fixture
def n1(make_user):
    return make_user("n1@lab.ma", first_name="Nadia")


@pytest.fixture
def n2(make_user):
    return make_user("n2@lab.ma", User.Role.SUPERVISOR)


@pytest.fixture
def admin_user(make_user):
    return make_user("admin@lab.ma", User.Role.ADMIN)


@pytest.fixture
def outsider(make_user):
    """A user who is in no escalation chain."""
    return make_user("other@lab.ma")


@pytest.fixture
def fridge(db, n1, n2):
    fridge = Fridge.objects.create(name="Frigo A")
    EscalationChain.objects.create(fridge=fridge, level=1, user=n1)
    EscalationChain.objects.create(fridge=fridge, level=2, user=n2)
    return fridge


@pytest.fixture
def other_fridge(db):
    return Fridge.objects.create(name="Frigo B")


@pytest.fixture
def device_and_key(fridge):
    device = Device(device_id="FRIGO-A", fridge=fridge)
    raw_key = device.rotate_api_key()
    device.save()
    return device, raw_key


@pytest.fixture
def api():
    """`api(user)` returns an APIClient authenticated as `user` (or anonymous)."""

    def make(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return make


class FakeNtfy:
    """Records ntfy publications instead of calling the network."""

    def __init__(self):
        self.calls = []
        self.fail = False

    def post(self, url, json=None, headers=None, timeout=None):
        if self.fail:
            raise ConnectionError("ntfy injoignable")
        self.calls.append({"url": url, "json": json, "headers": headers})

        class Response:
            def raise_for_status(self):
                pass

        return Response()


@pytest.fixture(autouse=True)
def ntfy(monkeypatch):
    fake = FakeNtfy()
    monkeypatch.setattr("incidents.notifiers.requests.post", fake.post)
    return fake
