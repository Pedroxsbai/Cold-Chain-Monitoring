from rest_framework import serializers

from .models import Incident, IncidentComment, Notification
from .services import can_acknowledge, can_close


def user_name(user):
    return (user.get_full_name() or user.email) if user else None


class IncidentCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = IncidentComment
        fields = ["id", "author", "author_name", "text", "created_at"]
        read_only_fields = ["author", "created_at"]

    def get_author_name(self, obj):
        return user_name(obj.author)


class NotificationSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "user", "user_name", "channel", "level", "status", "sent_at", "read_at"]

    def get_user_name(self, obj):
        return user_name(obj.user)


class IncidentSerializer(serializers.ModelSerializer):
    """Incident with the current user's allowed actions.

    Expects `levels` (fridge id → user's escalation level) in the context.
    """

    fridge_name = serializers.CharField(source="fridge.name", read_only=True)
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    remaining_minutes = serializers.FloatField(read_only=True)
    acked_by_name = serializers.SerializerMethodField()
    closed_by_name = serializers.SerializerMethodField()
    can_ack = serializers.SerializerMethodField()
    can_close = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = [
            "id",
            "fridge",
            "fridge_name",
            "type",
            "type_label",
            "status",
            "status_label",
            "started_at",
            "ended_at",
            "current_level",
            "notification_count",
            "last_notified_at",
            "excursion_minutes",
            "remaining_minutes",
            "severity_hours_reached",
            "reagents_compromised",
            "acked_by",
            "acked_by_name",
            "acked_at",
            "closed_by",
            "closed_by_name",
            "closed_at",
            "closing_comment",
            "can_ack",
            "can_close",
        ]

    def get_acked_by_name(self, obj):
        return user_name(obj.acked_by)

    def get_closed_by_name(self, obj):
        return user_name(obj.closed_by)

    def get_can_ack(self, obj):
        return can_acknowledge(obj)

    def get_can_close(self, obj):
        level = self.context.get("levels", {}).get(obj.fridge_id)
        return can_close(self.context["request"].user, obj, level)


class IncidentDetailSerializer(IncidentSerializer):
    comments = IncidentCommentSerializer(many=True, read_only=True)
    notifications = NotificationSerializer(many=True, read_only=True)

    class Meta(IncidentSerializer.Meta):
        fields = [*IncidentSerializer.Meta.fields, "comments", "notifications"]


class CloseIncidentSerializer(serializers.Serializer):
    comment = serializers.CharField(trim_whitespace=True)
