import re

import pytest

from accounts.models import User
from audit.models import EventLog

LOGIN = "/api/auth/login/"


def login(api, email="n1@lab.ma", password="S3cret-pass!"):
    return api().post(LOGIN, {"email": email, "password": password}, format="json")


def test_login_returns_tokens_and_profile(api, n1):
    response = login(api)
    assert response.status_code == 200
    assert response.data["user"]["email"] == "n1@lab.ma"
    assert response.data["user"]["role"] == "responsible"
    assert EventLog.objects.filter(type=EventLog.Type.USER_LOGIN, actor=n1).exists()
    n1.refresh_from_db()
    assert n1.last_login is not None


def test_failed_login_is_logged(api, n1):
    assert login(api, password="wrong").status_code == 401
    event = EventLog.objects.get(type=EventLog.Type.USER_LOGIN_FAILED)
    assert event.actor_label == "n1@lab.ma"


def test_login_is_throttled(api, n1):
    codes = [login(api, password="wrong").status_code for _ in range(11)]
    assert codes[-1] == 429


def test_logout_blacklists_refresh_token(api, n1):
    refresh = login(api).data["refresh"]
    assert api().post("/api/auth/logout/", {"refresh": refresh}).status_code == 200
    assert api().post("/api/auth/refresh/", {"refresh": refresh}).status_code == 401


def test_api_requires_authentication(api, db):
    assert api().get("/api/fridges/").status_code == 401


def test_profile_update_keeps_role(api, n1):
    response = api(n1).patch(
        "/api/auth/me/", {"phone": "+212600000000", "role": "admin"}, format="json"
    )
    assert response.status_code == 200
    n1.refresh_from_db()
    assert n1.phone == "+212600000000"
    assert n1.role == User.Role.RESPONSIBLE


def test_password_change(api, n1):
    response = api(n1).post(
        "/api/auth/password/change/",
        {"old_password": "S3cret-pass!", "new_password": "Nouveau-Pass-2026"},
    )
    assert response.status_code == 200
    assert login(api, password="Nouveau-Pass-2026").status_code == 200


def test_password_change_wrong_old_password(api, n1):
    response = api(n1).post(
        "/api/auth/password/change/", {"old_password": "nope", "new_password": "Nouveau-Pass-2026"}
    )
    assert response.status_code == 400


def test_password_reset_flow(api, n1, mailoutbox):
    response = api().post("/api/auth/password/reset/", {"email": "N1@lab.ma"})
    assert response.status_code == 200
    assert len(mailoutbox) == 1
    uid, token = re.search(r"uid=([\w-]+)&token=([\w-]+)", mailoutbox[0].body).groups()

    confirm = "/api/auth/password/reset/confirm/"
    weak = api().post(confirm, {"uid": uid, "token": token, "new_password": "123"})
    assert weak.status_code == 400
    ok = api().post(confirm, {"uid": uid, "token": token, "new_password": "Nouveau-Pass-2026"})
    assert ok.status_code == 200
    assert login(api, password="Nouveau-Pass-2026").status_code == 200
    # The link is single-use: the token depends on the password hash.
    reused = api().post(confirm, {"uid": uid, "token": token, "new_password": "Autre-Pass-2026"})
    assert reused.status_code == 400


def test_password_reset_unknown_email_same_reply(api, db, mailoutbox):
    response = api().post("/api/auth/password/reset/", {"email": "nobody@lab.ma"})
    assert response.status_code == 200
    assert mailoutbox == []


# --- User management (admin) -----------------------------------------------------------


def test_admin_creates_user(api, admin_user):
    response = api(admin_user).post(
        "/api/users/",
        {"email": "new@lab.ma", "first_name": "Sara", "role": "supervisor", "phone": "0600"},
        format="json",
    )
    assert response.status_code == 201
    assert "password" not in response.data
    user = User.objects.get(email="new@lab.ma")
    assert not user.has_usable_password()  # sets it through "mot de passe oublié"
    assert EventLog.objects.filter(type=EventLog.Type.OBJECT_CREATED, object_type="user").exists()


def test_admin_user_password_is_validated(api, admin_user):
    response = api(admin_user).post(
        "/api/users/", {"email": "new@lab.ma", "password": "123"}, format="json"
    )
    assert response.status_code == 400


def test_admin_cannot_delete_self(api, admin_user):
    assert api(admin_user).delete(f"/api/users/{admin_user.pk}/").status_code == 400


@pytest.mark.parametrize("method", ["get", "post"])
def test_n1_cannot_manage_users(api, n1, method):
    assert getattr(api(n1), method)("/api/users/").status_code == 403
