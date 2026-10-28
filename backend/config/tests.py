"""Production-hosting pieces: engine tick endpoint, React app serving, backups."""

import sqlite3
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from incidents.models import Incident

TICK = "/api/engine/tick/"


@pytest.fixture
def tick_token(settings):
    settings.COLDCHAIN = {**settings.COLDCHAIN, "ENGINE_TICK_TOKEN": "s3cret-tick"}
    return "s3cret-tick"


def test_tick_disabled_without_token(api, db):
    assert api().post(TICK).status_code == 404


def test_tick_rejects_wrong_token(api, tick_token):
    assert api().post(TICK, HTTP_X_ENGINE_TOKEN="nope").status_code == 403
    assert api().post(TICK).status_code == 403


def test_tick_runs_the_engine(api, tick_token, device_and_key):
    device, _ = device_and_key
    device.last_seen = timezone.now() - timedelta(hours=2)
    device.save()
    response = api().post(TICK, HTTP_X_ENGINE_TOKEN=tick_token)
    assert response.status_code == 200
    assert response.data["ok"] is True
    assert Incident.objects.get().type == Incident.Type.OFFLINE


@pytest.fixture
def frontend_build(settings, tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    settings.FRONTEND_DIST = tmp_path
    return tmp_path


def test_react_routes_return_index(client, frontend_build):
    for path in ["/", "/incidents/12", "/ack/abc:def", "/admin-ish"]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert b"id=root" in response.content
        assert response["Cache-Control"] == "no-cache"


def test_api_and_admin_are_not_swallowed(client, frontend_build, db):
    assert client.get("/api/does-not-exist/").status_code == 404
    assert client.get("/admin/").status_code == 302  # login redirect


def test_missing_build_is_explained(client, settings, tmp_path):
    settings.FRONTEND_DIST = tmp_path / "nothing"
    response = client.get("/")
    assert response.status_code == 503
    assert "npm run build" in response.content.decode()


# No surrounding test transaction: an open write transaction would block SQLite's
# backup reader on the shared in-memory test database (not an issue on a file).
@pytest.mark.django_db(transaction=True)
def test_backup_db_keeps_the_last_n(settings, tmp_path):
    from monitoring.models import Fridge

    Fridge.objects.create(name="Frigo A")
    settings.COLDCHAIN = {**settings.COLDCHAIN, "BACKUP_DIR": str(tmp_path), "BACKUP_KEEP": 2}
    for name in ["db-20260101-0000.sqlite3", "db-20260102-0000.sqlite3"]:
        (tmp_path / name).write_bytes(b"old")
    call_command("backup_db")
    backups = sorted(tmp_path.glob("db-*.sqlite3"))
    assert len(backups) == 2
    newest = backups[-1]
    with sqlite3.connect(newest) as db:
        names = [row[0] for row in db.execute("select name from monitoring_fridge")]
    assert names == ["Frigo A"]
