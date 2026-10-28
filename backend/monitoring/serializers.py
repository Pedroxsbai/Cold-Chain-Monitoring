from rest_framework import serializers

from incidents.models import Incident

from .models import Device, EscalationChain, Fridge, Measurement
from .services import THRESHOLD_FIELDS, fridge_status


class ThresholdValidationMixin:
    """Check min < max on the merged (instance + submitted) thresholds."""

    def validate(self, attrs):
        attrs = super().validate(attrs)

        def value(field):
            if field in attrs:
                return attrs[field]
            if self.instance is not None:
                return getattr(self.instance, field)
            return Fridge._meta.get_field(field).get_default()

        errors = {}
        if value("temp_min") >= value("temp_max"):
            errors["temp_max"] = "La température max doit être supérieure à la température min."
        hum_min, hum_max = value("hum_min"), value("hum_max")
        if hum_min is not None and hum_max is not None and hum_min >= hum_max:
            errors["hum_max"] = "L'humidité max doit être supérieure à l'humidité min."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class IncidentSummarySerializer(serializers.ModelSerializer):
    remaining_minutes = serializers.FloatField(read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id",
            "type",
            "status",
            "started_at",
            "current_level",
            "excursion_minutes",
            "remaining_minutes",
            "reagents_compromised",
        ]


class FridgeSerializer(ThresholdValidationMixin, serializers.ModelSerializer):
    device = serializers.SerializerMethodField()
    last_measurement = serializers.SerializerMethodField()
    open_incident = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Fridge
        fields = [
            "id",
            "name",
            "location",
            *THRESHOLD_FIELDS,
            "is_active",
            "created_at",
            "device",
            "last_measurement",
            "open_incident",
            "status",
        ]

    # Dashboard data comes from `with_dashboard_data` annotations when available,
    # with a fallback query for freshly created / updated instances.

    def _unfinished_incident(self, obj):
        if hasattr(obj, "unfinished_incidents"):
            return obj.unfinished_incidents[0] if obj.unfinished_incidents else None
        return obj.incidents.filter(ended_at__isnull=True).first()

    def _last_measurement(self, obj):
        if hasattr(obj, "last_measurement_at"):
            if obj.last_measurement_at is None:
                return None
            return {
                "temperature": obj.last_temperature,
                "humidity": obj.last_humidity,
                "sensor_ok": obj.last_sensor_ok,
                "received_at": obj.last_measurement_at,
            }
        m = obj.measurements.order_by("-received_at").first()
        if m is None:
            return None
        return {
            "temperature": m.temperature,
            "humidity": m.humidity,
            "sensor_ok": m.sensor_ok,
            "received_at": m.received_at,
        }

    def get_device(self, obj):
        device = getattr(obj, "device", None)
        if device is None:
            return None
        return {
            "id": device.id,
            "device_id": device.device_id,
            "status": device.status,
            "last_seen": device.last_seen,
            "firmware": device.firmware,
        }

    def get_last_measurement(self, obj):
        last = self._last_measurement(obj)
        if last is not None:
            last["received_at"] = serializers.DateTimeField().to_representation(last["received_at"])
        return last

    def get_open_incident(self, obj):
        incident = self._unfinished_incident(obj)
        return IncidentSummarySerializer(incident).data if incident else None

    def get_status(self, obj):
        last = self._last_measurement(obj)
        return fridge_status(
            last_measurement_at=last["received_at"] if last else None,
            unfinished_incident=self._unfinished_incident(obj),
            device=getattr(obj, "device", None),
        )


class ThresholdSerializer(ThresholdValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Fridge
        fields = list(THRESHOLD_FIELDS)


class MeasurementSerializer(serializers.ModelSerializer):
    fridge_name = serializers.CharField(source="fridge.name", read_only=True)
    device_id = serializers.CharField(source="device.device_id", read_only=True, default=None)

    class Meta:
        model = Measurement
        fields = [
            "id",
            "fridge",
            "fridge_name",
            "device_id",
            "temperature",
            "humidity",
            "sensor_ok",
            "received_at",
        ]


class MeasurementIngestSerializer(serializers.Serializer):
    """Payload sent by a node. The server sets the timestamp on reception."""

    device_id = serializers.CharField(max_length=50)
    temperature = serializers.FloatField(
        required=False, allow_null=True, min_value=-50, max_value=80
    )
    humidity = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=100)
    sensor_ok = serializers.BooleanField(default=True)
    firmware = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate(self, attrs):
        if attrs["sensor_ok"] and (
            attrs.get("temperature") is None or attrs.get("humidity") is None
        ):
            raise serializers.ValidationError(
                "temperature et humidity sont obligatoires quand sensor_ok vaut true."
            )
        return attrs


class DeviceSerializer(serializers.ModelSerializer):
    fridge_name = serializers.CharField(source="fridge.name", read_only=True, default=None)

    class Meta:
        model = Device
        fields = [
            "id",
            "device_id",
            "fridge",
            "fridge_name",
            "status",
            "last_seen",
            "firmware",
            "created_at",
        ]
        read_only_fields = ["status", "last_seen", "firmware", "created_at"]


class EscalationChainSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = EscalationChain
        fields = ["id", "fridge", "level", "user", "user_email", "user_name"]
