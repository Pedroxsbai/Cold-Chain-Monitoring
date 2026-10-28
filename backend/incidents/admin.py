from django.contrib import admin

from .models import Incident, IncidentComment, Notification


class CommentInline(admin.TabularInline):
    model = IncidentComment
    extra = 0


class NotificationInline(admin.TabularInline):
    model = Notification
    extra = 0
    readonly_fields = ["user", "channel", "level", "status", "sent_at", "read_at", "error"]
    can_delete = False


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "fridge",
        "type",
        "status",
        "started_at",
        "ended_at",
        "current_level",
        "excursion_minutes",
        "reagents_compromised",
    ]
    list_filter = ["status", "type", "fridge", "reagents_compromised"]
    date_hierarchy = "started_at"
    inlines = [CommentInline, NotificationInline]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "incident", "user", "channel", "level", "status"]
    list_filter = ["channel", "status", "level"]
