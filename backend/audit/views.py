from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdminRole
from common.dates import filter_date_range

from .models import EventLog


class EventLogSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = EventLog
        fields = [
            "id",
            "timestamp",
            "type",
            "type_label",
            "actor",
            "actor_label",
            "object_type",
            "object_id",
            "object_repr",
            "details",
        ]


class EventLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Audit trail (admin, read-only).

    Filters: `?type=&actor=&object_type=&object_id=&from=&to=`.
    """

    serializer_class = EventLogSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filterset_fields = ["type", "actor", "object_type", "object_id"]

    def get_queryset(self):
        return filter_date_range(EventLog.objects.all(), "timestamp", self.request.query_params)
