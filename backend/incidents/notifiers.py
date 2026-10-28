"""Notification channels.

Each channel implements `Notifier.send(notification, message)` and raises on failure.
The escalation engine only deals with this interface, so adding a channel (SMS gateway,
GSM call, ...) means writing a new class and registering it in `NOTIFIERS`.
"""

from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


@dataclass
class Message:
    title: str
    body: str
    urgent: bool = False
    # Per-notification links; None for informational messages (end of incident).
    ack_api_url: str | None = None
    ack_page_url: str | None = None


class Notifier:
    channel: str

    def send(self, notification, message):
        raise NotImplementedError


class NtfyNotifier(Notifier):
    """Push notification through ntfy, with a « Je prends en charge » action button."""

    channel = Notification.Channel.NTFY
    timeout = 10

    def send(self, notification, message):
        config = settings.COLDCHAIN
        payload = {
            "topic": notification.user.ntfy_topic,
            "title": message.title,
            "message": message.body,
            "priority": 5 if message.urgent else 4,
            "tags": ["rotating_light" if message.urgent else "warning"]
            if message.ack_api_url
            else ["white_check_mark"],
        }
        if message.ack_api_url:
            payload["click"] = message.ack_page_url
            payload["actions"] = [
                {
                    "action": "http",
                    "label": "Je prends en charge",
                    "url": message.ack_api_url,
                    "method": "POST",
                    "clear": True,
                },
                {"action": "view", "label": "Ouvrir", "url": message.ack_page_url},
            ]
        headers = (
            {"Authorization": f"Bearer {config['NTFY_TOKEN']}"} if config["NTFY_TOKEN"] else {}
        )
        response = requests.post(
            config["NTFY_SERVER"].rstrip("/"), json=payload, headers=headers, timeout=self.timeout
        )
        response.raise_for_status()


class EmailNotifier(Notifier):
    channel = Notification.Channel.EMAIL

    def send(self, notification, message):
        body = message.body
        if message.ack_page_url:
            body += f"\n\nPrendre en charge l'incident :\n{message.ack_page_url}"
        send_mail(f"[Cold Chain] {message.title}", body, None, [notification.user.email])


NOTIFIERS = {notifier.channel: notifier for notifier in (NtfyNotifier(), EmailNotifier())}


def channels_for(user):
    """Channels on which `user` can be reached, among the enabled ones."""
    reachable = {
        Notification.Channel.NTFY: bool(user.ntfy_topic),
        Notification.Channel.EMAIL: bool(user.email),
    }
    return [
        channel
        for channel in settings.COLDCHAIN["NOTIFY_CHANNELS"]
        if channel in NOTIFIERS and reachable.get(channel)
    ]
