from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from accounts.views import (
    LoginView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfileView,
    UserViewSet,
)
from audit.views import EventLogViewSet
from incidents.views import IncidentViewSet
from monitoring.views import (
    DeviceViewSet,
    EscalationChainViewSet,
    FridgeViewSet,
    MeasurementView,
)

router = DefaultRouter()
router.register("fridges", FridgeViewSet, basename="fridge")
router.register("devices", DeviceViewSet, basename="device")
router.register("escalation", EscalationChainViewSet, basename="escalation")
router.register("incidents", IncidentViewSet, basename="incident")
router.register("events", EventLogViewSet, basename="event")
router.register("users", UserViewSet, basename="user")

auth_patterns = [
    path("login/", LoginView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="logout"),
    path("me/", ProfileView.as_view(), name="profile"),
    path("password/change/", PasswordChangeView.as_view(), name="password_change"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path(
        "password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include(auth_patterns)),
    path("api/measurements/", MeasurementView.as_view(), name="measurements"),
    path("api/", include(router.urls)),
]
