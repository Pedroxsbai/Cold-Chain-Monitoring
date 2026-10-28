from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.views import TokenObtainPairView

from audit.mixins import AuditedModelViewSetMixin
from audit.models import EventLog
from audit.services import log_event

from .models import User
from .permissions import IsAdminRole
from .serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    UserSerializer,
)

RESET_REQUEST_REPLY = "Si un compte existe pour cette adresse, un e-mail vient d'être envoyé."


def revoke_refresh_tokens(user):
    """Blacklist every outstanding refresh token of a user (forces re-login)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET / PATCH the logged-in user's profile and notification channels."""

    serializer_class = ProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        revoke_refresh_tokens(request.user)
        log_event(
            EventLog.Type.PASSWORD_RESET, actor=request.user, obj=request.user, step="changed"
        )
        return Response({"detail": "Mot de passe modifié. Reconnectez-vous."})


class PasswordResetRequestView(APIView):
    """Send a reset link by e-mail. Same reply whether the account exists or not."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_active=True
        ).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            base_url = settings.COLDCHAIN["PUBLIC_BASE_URL"].rstrip("/")
            link = f"{base_url}/reinitialiser-mot-de-passe?uid={uid}&token={token}"
            send_mail(
                "Cold Chain Monitoring — réinitialisation du mot de passe",
                "Bonjour,\n\nPour choisir un nouveau mot de passe, ouvrez ce lien :\n"
                f"{link}\n\nSi vous n'êtes pas à l'origine de cette demande, ignorez ce message.",
                None,
                [user.email],
            )
            log_event(EventLog.Type.PASSWORD_RESET, obj=user, step="requested")
        return Response({"detail": RESET_REQUEST_REPLY})


class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = User.objects.get(
                pk=force_str(urlsafe_base64_decode(data["uid"])), is_active=True
            )
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if user is None or not default_token_generator.check_token(user, data["token"]):
            return Response(
                {"detail": "Lien invalide ou expiré."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            validate_password(data["new_password"], user=user)
        except DjangoValidationError as error:
            return Response({"new_password": error.messages}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        revoke_refresh_tokens(user)
        log_event(EventLog.Type.PASSWORD_RESET, obj=user, step="completed")
        return Response({"detail": "Mot de passe réinitialisé. Vous pouvez vous connecter."})


class UserViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """User management (admin). Filters: `?role=&is_active=`."""

    queryset = User.objects.order_by("email")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filterset_fields = ["role", "is_active"]

    def destroy(self, request, *args, **kwargs):
        if self.get_object() == request.user:
            return Response(
                {"detail": "Vous ne pouvez pas supprimer votre propre compte."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)
