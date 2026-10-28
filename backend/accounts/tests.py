import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User


@pytest.mark.django_db
def test_create_user_with_email():
    user = User.objects.create_user(email="n1@lab.ma", password="S3cret-pass!")
    assert user.email == "n1@lab.ma"
    assert user.role == User.Role.RESPONSIBLE
    assert not user.is_admin


@pytest.mark.django_db
def test_superuser_is_admin():
    user = User.objects.create_superuser(email="admin@lab.ma", password="S3cret-pass!")
    assert user.role == User.Role.ADMIN
    assert user.is_admin


@pytest.mark.django_db
def test_jwt_login_with_email():
    User.objects.create_user(email="n1@lab.ma", password="S3cret-pass!")
    response = APIClient().post(
        reverse("token_obtain_pair"),
        {"email": "n1@lab.ma", "password": "S3cret-pass!"},
        format="json",
    )
    assert response.status_code == 200
    assert "access" in response.data and "refresh" in response.data
