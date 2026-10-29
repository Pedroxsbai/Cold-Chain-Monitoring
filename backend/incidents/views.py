import hmac

from django.conf import settings
from django.http import Http404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView


from audit.models import EventLog
from audit.services import log_event
from common.dates import filter_date_range
from monitoring.services import fridges_for

from . import ack, engine, services
from .daily_backup import daily_backup_if_due
from .models import Incident, Notification
from .serializers import (
    CloseIncidentSerializer,
    IncidentCommentSerializer,
    IncidentDetailSerializer,
    IncidentSerializer,
)


class IncidentViewSet(viewsets.ReadOnlyModelViewSet):
    """Incidents of the user's fridges.

    Filters: `?fridge=&type=&status=&active=true&from=&to=` (on `started_at`).
    """

    filterset_fields = ["fridge", "type", "status", "reagents_compromised"]

    def get_queryset(self):
        queryset = Incident.objects.filter(
            fridge__in=fridges_for(self.request.user)
        ).select_related("fridge", "acked_by", "closed_by")
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("comments__author", "notifications__user")
        if self.request.query_params.get("active") in ("1", "true"):
            queryset = queryset.filter(ended_at__isnull=True)
        return filter_date_range(queryset, "started_at", self.request.query_params)

    def get_serializer_class(self):
        return IncidentDetailSerializer if self.action == "retrieve" else IncidentSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context["levels"] = services.user_levels(self.request.user)
        return context

    def _detail_response(self, incident, status_code=status.HTTP_200_OK):
        serializer = IncidentDetailSerializer(incident, context=self.get_serializer_context())
        return Response(serializer.data, status=status_code)

    def _conflict(self, error):
        return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)

    @action(detail=True, methods=["post"])
    def ack(self, request, pk=None):
        incident = self.get_object()
        try:
            services.acknowledge(incident, request.user, via="app")
        except services.IncidentActionError as error:
            return self._conflict(error)
        return self._detail_response(incident)

    @action(detail=True, methods=["post"])
    def comments(self, request, pk=None):
        incident = self.get_object()
        serializer = IncidentCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = services.add_comment(incident, request.user, serializer.validated_data["text"])
        return Response(IncidentCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        incident = self.get_object()
        level = services.user_levels(request.user).get(incident.fridge_id)
        if not (request.user.is_admin or (level or 0) >= 2):
            raise PermissionDenied("La clôture est réservée au niveau N2 et à l'administrateur.")
        serializer = CloseIncidentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.close(incident, request.user, serializer.validated_data["comment"])
        except services.IncidentActionError as error:
            return self._conflict(error)
        return self._detail_response(incident)


class AckLinkView(APIView):
    """Public page behind the link of a notification (no login needed on the phone).

    GET shows the incident and records that the notification was opened — which does
    NOT stop the escalation. POST takes charge, once per link.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ack"

    def get_notification(self, token):
        notification_id = ack.read_token(token)
        if notification_id is None:
            return None
        return (
            Notification.objects.select_related("incident__fridge", "user")
            .filter(pk=notification_id, user__is_active=True)
            .first()
        )

    def invalid(self):
        return Response({"detail": "Lien invalide ou expiré."}, status=status.HTTP_400_BAD_REQUEST)

    def describe(self, notification):
        incident = notification.incident
        return {
            "incident": {
                "id": incident.id,
                "fridge_name": incident.fridge.name,
                "type": incident.type,
                "type_label": incident.get_type_display(),
                "status": incident.status,
                "status_label": incident.get_status_display(),
                "started_at": incident.started_at,
                "ended_at": incident.ended_at,
                "current_level": incident.current_level,
                "excursion_minutes": incident.total_excursion_minutes(),
                "remaining_minutes": incident.remaining_minutes,
                "max_excursion_hours": incident.fridge.max_excursion_hours,
                "reagents_compromised": incident.reagents_compromised,
            },
            "recipient": notification.user.get_full_name() or notification.user.email,
            "link_used": notification.ack_used_at is not None,
            "can_ack": notification.ack_used_at is None and services.can_acknowledge(incident),
        }

    def get(self, request, token):
        notification = self.get_notification(token)
        if notification is None:
            return self.invalid()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
            log_event(
                EventLog.Type.NOTIFICATION_READ,
                actor=notification.user,
                obj=notification.incident,
                channel=notification.channel,
            )
        return Response(self.describe(notification))

    def post(self, request, token):
        notification = self.get_notification(token)
        if notification is None:
            return self.invalid()
        if notification.ack_used_at is not None:
            return Response(
                {"detail": "Ce lien a déjà été utilisé."}, status=status.HTTP_409_CONFLICT
            )
        try:
            services.acknowledge(notification.incident, notification.user, via=notification.channel)
        except services.IncidentActionError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        now = timezone.now()
        notification.ack_used_at = now
        notification.read_at = notification.read_at or now
        notification.save(update_fields=["ack_used_at", "read_at"])
        return Response(self.describe(notification))


class EngineTickView(APIView):
    """Run one cycle of the alert engine (offline detection, escalation, notifications).

    For hosts without a permanent process: an external cron service calls it every
    minute with the `X-Engine-Token` header. Disabled when ENGINE_TICK_TOKEN is empty.

    The same tick also makes the daily SQLite backup (first tick after 03:00), since
    scheduled tasks are not available on a free PythonAnywhere account.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        expected = settings.COLDCHAIN["ENGINE_TICK_TOKEN"]
        if not expected:
            raise Http404
        given = request.META.get("HTTP_X_ENGINE_TOKEN", "")
        if not hmac.compare_digest(given.encode(), expected.encode()):
            return Response({"detail": "Jeton invalide."}, status=status.HTTP_403_FORBIDDEN)
        started = timezone.now()
        engine.tick(started)
        backup_done = daily_backup_if_due()
        return Response(
            {
                "ok": True,
                "at": started,
                "duration_ms": round((timezone.now() - started).total_seconds() * 1000),
                "unfinished_incidents": Incident.objects.filter(ended_at__isnull=True).count(),
                "backup_done": backup_done,
            }
        )