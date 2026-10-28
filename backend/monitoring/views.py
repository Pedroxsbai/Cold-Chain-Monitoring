import csv
from datetime import timedelta

from django.db import transaction
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.permissions import IsAdminRole
from audit.mixins import AuditedModelViewSetMixin
from audit.models import EventLog
from audit.services import log_event
from common.dates import date_range_from_params, filter_date_range

from .authentication import DeviceKeyAuthentication
from .models import Device, EscalationChain, Measurement
from .serializers import (
    DeviceSerializer,
    EscalationChainSerializer,
    FridgeSerializer,
    MeasurementIngestSerializer,
    MeasurementSerializer,
    ThresholdSerializer,
)
from .services import (
    fridges_for,
    log_threshold_changes,
    record_measurement,
    threshold_snapshot,
    with_dashboard_data,
)

DEFAULT_SERIES_WINDOW = timedelta(hours=24)
MAX_SERIES_WINDOW = timedelta(days=366)


def series_bounds(params):
    """Bounds for a chart series: defaults to the last 24 h, capped to one year."""
    start, end = date_range_from_params(params)
    end = end or timezone.now()
    start = start or end - DEFAULT_SERIES_WINDOW
    if end - start > MAX_SERIES_WINDOW:
        raise ValidationError({"from": "La période demandée ne peut pas dépasser un an."})
    return start, end


class FridgeViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """Fridges with their live status. Read for everyone in the chain, write for admins."""

    serializer_class = FridgeSerializer
    filterset_fields = ["is_active"]
    read_actions = {"list", "retrieve", "measurements", "export"}

    def get_queryset(self):
        return with_dashboard_data(fridges_for(self.request.user))

    def get_permissions(self):
        if self.action in self.read_actions:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminRole()]

    def perform_update(self, serializer):
        before = threshold_snapshot(serializer.instance)
        super().perform_update(serializer)
        log_threshold_changes(before, serializer.instance, self.request.user)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Ce frigo a un historique de mesures : désactivez-le plutôt."},
                status=status.HTTP_409_CONFLICT,
            )

    @action(detail=True, methods=["patch"])
    def thresholds(self, request, pk=None):
        fridge = self.get_object()
        before = threshold_snapshot(fridge)
        serializer = ThresholdSerializer(fridge, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_threshold_changes(before, fridge, request.user)
        return Response(FridgeSerializer(self.get_object()).data)

    def _measurements_in_range(self, fridge):
        start, end = series_bounds(self.request.query_params)
        queryset = fridge.measurements.filter(received_at__gte=start, received_at__lte=end)
        return queryset.order_by("received_at"), start, end

    @action(detail=True, methods=["get"])
    def measurements(self, request, pk=None):
        """Full (unpaginated) series for the charts. `?from=&to=`, default last 24 h."""
        fridge = self.get_object()
        queryset, start, end = self._measurements_in_range(fridge)
        results = list(queryset.values("id", "temperature", "humidity", "sensor_ok", "received_at"))
        return Response(
            {
                "fridge": fridge.id,
                "from": start,
                "to": end,
                "count": len(results),
                "results": results,
            }
        )

    @action(detail=True, methods=["get"], url_path="measurements/export")
    def export(self, request, pk=None):
        """CSV export (Excel-friendly in French: `;` separator, decimal comma)."""
        fridge = self.get_object()
        queryset, start, end = self._measurements_in_range(fridge)

        def number(value):
            return "" if value is None else str(value).replace(".", ",")

        filename = f"{slugify(fridge.name)}_{start:%Y%m%d}-{end:%Y%m%d}.csv"
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("﻿")  # BOM so Excel detects UTF-8
        writer = csv.writer(response, delimiter=";")
        writer.writerow(["date", "temperature_c", "humidite_pct", "capteur_ok"])
        for m in queryset.iterator():
            writer.writerow(
                [
                    timezone.localtime(m.received_at).strftime("%Y-%m-%d %H:%M:%S"),
                    number(m.temperature),
                    number(m.humidity),
                    "oui" if m.sensor_ok else "non",
                ]
            )
        return response


class MeasurementPermission(BasePermission):
    """POST is reserved to IoT nodes (device key), GET to logged-in users (JWT)."""

    def has_permission(self, request, view):
        if request.method == "POST":
            return isinstance(request.auth, Device)
        return bool(request.user and request.user.is_authenticated)


class MeasurementView(generics.ListCreateAPIView):
    """POST: a node sends a reading. GET: paginated history (`?fridge=&from=&to=`)."""

    authentication_classes = [JWTAuthentication, DeviceKeyAuthentication]
    permission_classes = [MeasurementPermission]
    serializer_class = MeasurementSerializer
    filterset_fields = ["fridge"]

    def get_queryset(self):
        queryset = Measurement.objects.filter(
            fridge__in=fridges_for(self.request.user)
        ).select_related("fridge", "device")
        return filter_date_range(queryset, "received_at", self.request.query_params)

    def create(self, request, *args, **kwargs):
        device = request.auth
        serializer = MeasurementIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if device.fridge is None:
            return Response(
                {"detail": "Ce nœud n'est rattaché à aucun frigo."},
                status=status.HTTP_409_CONFLICT,
            )
        data = serializer.validated_data
        measurement = record_measurement(
            device,
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            sensor_ok=data["sensor_ok"],
            firmware=data.get("firmware", ""),
        )
        return Response(
            {"id": measurement.id, "received_at": measurement.received_at},
            status=status.HTTP_201_CREATED,
        )


class DeviceViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """IoT nodes (admin). The API key is returned once, at creation or rotation."""

    queryset = Device.objects.select_related("fridge")
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filterset_fields = ["status", "fridge"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            device = serializer.save()
            raw_key = device.rotate_api_key()
            device.save(update_fields=["api_key_hash"])
            log_event(EventLog.Type.OBJECT_CREATED, actor=request.user, obj=device)
        return Response({**serializer.data, "api_key": raw_key}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="rotate-key")
    def rotate_key(self, request, pk=None):
        device = self.get_object()
        raw_key = device.rotate_api_key()
        device.save(update_fields=["api_key_hash"])
        log_event(EventLog.Type.OBJECT_UPDATED, actor=request.user, obj=device, action="rotate_key")
        return Response({"api_key": raw_key})


class EscalationChainViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """Who is notified at each level for each fridge (admin)."""

    queryset = EscalationChain.objects.select_related("fridge", "user")
    serializer_class = EscalationChainSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filterset_fields = ["fridge", "level", "user"]
