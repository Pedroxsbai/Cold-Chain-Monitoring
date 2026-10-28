from datetime import datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.exceptions import ValidationError


def parse_bound(value, name, *, end_of_day=False):
    """Parse an ISO 8601 datetime or a plain date (YYYY-MM-DD) into an aware datetime.

    A plain date means the start of that day, or its end when `end_of_day` is set,
    so that `?from=2026-10-01&to=2026-10-01` covers the whole day.
    """
    try:
        dt = parse_datetime(value)
        if dt is None:
            day = parse_date(value)
            if day is None:
                raise ValueError
            dt = datetime.combine(day, time.max if end_of_day else time.min)
    except ValueError:
        raise ValidationError({name: "Format attendu : AAAA-MM-JJ ou date ISO 8601."}) from None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def date_range_from_params(params):
    """Return the (from, to) bounds given in query params, each possibly None."""
    start = params.get("from")
    end = params.get("to")
    start = parse_bound(start, "from") if start else None
    end = parse_bound(end, "to", end_of_day=True) if end else None
    if start and end and start > end:
        raise ValidationError({"to": "La date de fin doit être postérieure à la date de début."})
    return start, end


def filter_date_range(queryset, field, params):
    start, end = date_range_from_params(params)
    if start:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end:
        queryset = queryset.filter(**{f"{field}__lte": end})
    return queryset
