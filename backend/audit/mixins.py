from django.db import transaction

from .models import EventLog
from .services import log_event


class AuditedModelViewSetMixin:
    """Write an EventLog entry for every create, update and delete of a viewset."""

    def perform_create(self, serializer):
        obj = serializer.save()
        log_event(EventLog.Type.OBJECT_CREATED, actor=self.request.user, obj=obj)

    def perform_update(self, serializer):
        fields = sorted(set(serializer.validated_data) - {"password"})
        obj = serializer.save()
        log_event(EventLog.Type.OBJECT_UPDATED, actor=self.request.user, obj=obj, fields=fields)

    def perform_destroy(self, instance):
        # Log first (the object still has its pk); roll back the log if deletion fails.
        with transaction.atomic():
            log_event(EventLog.Type.OBJECT_DELETED, actor=self.request.user, obj=instance)
            instance.delete()
