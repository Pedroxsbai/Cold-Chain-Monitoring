from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Manager for a user model that logs in with its e-mail address."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Application user. The escalation level (N1/N2/N3) is carried by each
    fridge's escalation chain; `role` is the global account role."""

    class Role(models.TextChoices):
        RESPONSIBLE = "responsible", "Responsable frigo"
        SUPERVISOR = "supervisor", "Supérieur"
        ADMIN = "admin", "Administrateur"

    username = None
    email = models.EmailField("adresse e-mail", unique=True)
    phone = models.CharField("téléphone", max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.RESPONSIBLE)
    ntfy_topic = models.CharField("topic ntfy", max_length=100, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser
