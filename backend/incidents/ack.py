"""Signed acknowledgement links, one per notification.

The token carries the notification id, signed with SECRET_KEY and timestamped; it expires
after ACK_LINK_MAX_AGE_HOURS and works once (`Notification.ack_used_at`).
"""

from django.conf import settings
from django.core import signing

SALT = "coldchain.incident-ack"


def make_token(notification):
    return signing.dumps(notification.pk, salt=SALT)


def read_token(token):
    """Return the notification id, or None if the token is invalid or expired."""
    max_age = settings.COLDCHAIN["ACK_LINK_MAX_AGE_HOURS"] * 3600
    try:
        return signing.loads(token, salt=SALT, max_age=max_age)
    except signing.BadSignature:  # also covers SignatureExpired
        return None


def ack_urls(notification):
    """(API url for one-tap buttons, frontend page url) of a notification's link."""
    token = make_token(notification)
    config = settings.COLDCHAIN
    api_url = f"{config['API_BASE_URL'].rstrip('/')}/api/ack/{token}/"
    page_url = f"{config['PUBLIC_BASE_URL'].rstrip('/')}/ack/{token}"
    return api_url, page_url
