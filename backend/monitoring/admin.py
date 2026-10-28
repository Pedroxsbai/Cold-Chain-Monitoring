from django.contrib import admin, messages

from audit.models import EventLog
from audit.services import log_event

from .models import Device, EscalationChain, Fridge, Measurement

THRESHOLD_FIELDS = ["temp_min", "temp_max", "hum_min", "hum_max", "max_excursion_hours"]


class EscalationInline(admin.TabularInline):
    model = EscalationChain
    extra = 1
    autocomplete_fields = ["user"]


@admin.register(Fridge)
class FridgeAdmin(admin.ModelAdmin):
    list_display = ["name", "location", "temp_min", "temp_max", "hum_min", "hum_max", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "location"]
    inlines = [EscalationInline]

    def save_model(self, request, obj, form, change):
        changed = [f for f in THRESHOLD_FIELDS if f in form.changed_data] if change else []
        old = Fridge.objects.get(pk=obj.pk) if changed else None
        super().save_model(request, obj, form, change)
        if changed:
            log_event(
                EventLog.Type.THRESHOLD_CHANGED,
                actor=request.user,
                obj=obj,
                changes={f: [getattr(old, f), getattr(obj, f)] for f in changed},
            )


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ["device_id", "fridge", "status", "last_seen", "firmware"]
    list_filter = ["status"]
    search_fields = ["device_id"]
    readonly_fields = ["last_seen", "firmware", "status", "created_at"]
    actions = ["regenerate_api_key"]

    def save_model(self, request, obj, form, change):
        raw_key = obj.rotate_api_key() if not change else None
        super().save_model(request, obj, form, change)
        if raw_key:
            self._show_key(request, obj, raw_key)

    @admin.action(description="Régénérer la clé API")
    def regenerate_api_key(self, request, queryset):
        for device in queryset:
            raw_key = device.rotate_api_key()
            device.save(update_fields=["api_key_hash"])
            self._show_key(request, device, raw_key)

    def _show_key(self, request, device, raw_key):
        self.message_user(
            request,
            f"Clé API de {device.device_id} (affichée une seule fois) : {raw_key}",
            messages.WARNING,
        )


@admin.register(EscalationChain)
class EscalationChainAdmin(admin.ModelAdmin):
    list_display = ["fridge", "level", "user"]
    list_filter = ["fridge", "level"]
    autocomplete_fields = ["user"]


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ["received_at", "fridge", "temperature", "humidity", "sensor_ok", "device"]
    list_filter = ["fridge", "sensor_ok"]
    date_hierarchy = "received_at"
