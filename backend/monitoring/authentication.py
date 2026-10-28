from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from audit.models import EventLog
from audit.services import log_event

from .models import Device


class DeviceKeyAuthentication(BaseAuthentication):
    """Authenticate an IoT node by `device_id` (JSON body) + `X-Device-Key` header.

    On success `request.user` is anonymous and `request.auth` is the Device.
    """

    def authenticate(self, request):
        raw_key = request.META.get("HTTP_X_DEVICE_KEY")
        if not raw_key:
            return None

        device_id = request.data.get("device_id") if hasattr(request.data, "get") else None
        device = (
            Device.objects.select_related("fridge").filter(device_id=device_id).first()
            if device_id
            else None
        )
        if device is None or not device.check_api_key(raw_key):
            log_event(
                EventLog.Type.DEVICE_KEY_REJECTED,
                actor_label=str(device_id or "?")[:150],
                ip=request.META.get("REMOTE_ADDR"),
            )
            raise AuthenticationFailed("Clé de nœud invalide.")
        return (AnonymousUser(), device)

    def authenticate_header(self, request):
        return "X-Device-Key"
