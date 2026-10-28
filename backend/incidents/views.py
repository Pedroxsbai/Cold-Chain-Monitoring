from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from common.dates import filter_date_range
from monitoring.services import fridges_for

from . import services
from .models import Incident
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
