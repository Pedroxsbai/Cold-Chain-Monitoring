from django.contrib import admin, messages

from .models import Device, EscalationChain, Fridge, Measurement
from .services import log_threshold_changes, threshold_snapshot


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
        before = threshold_snapshot(Fridge.objects.get(pk=obj.pk)) if change else None
        super().save_model(request, obj, form, change)
        if before is not None:
            log_threshold_changes(before, obj, request.user)


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
