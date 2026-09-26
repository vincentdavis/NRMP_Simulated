"""Rate limits counted in the database (plan step 2.5; CRIT-6, ENG-5).

A limit such as "10/h" allows 10 events per key in each fixed window of an hour. Each key and window has one row,
incremented with an atomic UPDATE, so the count is exact across processes without a shared cache (the project has no
Redis, decision D5, and Django's database cache does not increment atomically).
"""

import functools
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import RateLimitCounter
from .security import client_ip

logger = logging.getLogger(__name__)

PERIODS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
MESSAGE = "Too many requests. Please wait a little and try again."


def parse_rate(rate: str) -> tuple[int, int]:
    """Return (events, seconds) for a rate such as "10/h"; raise ValueError for anything else."""
    count, _, period = rate.partition("/")
    if not count.isdigit() or period not in PERIODS:
        raise ValueError(f"Invalid rate {rate!r}; use a count and s, m, h or d, for example 10/h.")
    return int(count), PERIODS[period]


def window_start(seconds: int, now: datetime | None = None) -> datetime:
    """Return the start of the fixed window of `seconds` that contains `now`."""
    stamp = int((now or datetime.now(UTC)).timestamp())
    return datetime.fromtimestamp(stamp - stamp % seconds, tz=UTC)


def hit(key: str, rate: str) -> bool:
    """Count one event for `key`; return True if that goes over `rate`."""
    limit, seconds = parse_rate(rate)
    start = window_start(seconds)
    rows = RateLimitCounter.objects.filter(key=key, window_start=start)
    with transaction.atomic():
        if not rows.update(count=F("count") + 1):
            try:
                with transaction.atomic():
                    RateLimitCounter.objects.create(key=key, window_start=start, count=1)
            except IntegrityError:  # another request created the row first
                rows.update(count=F("count") + 1)
        count = rows.values_list("count", flat=True).get()
    return count > limit


def too_many_requests(request: HttpRequest) -> HttpResponse:
    """Return the 429 response: plain text for HTMX (the page shows a toast), a page otherwise."""
    if getattr(request, "htmx", False):
        return HttpResponse(MESSAGE, status=429)
    return render(request, "429.html", {"message": MESSAGE}, status=429)


def over_limit(request: HttpRequest, name: str, *, by: str) -> bool:
    """Count one event of kind `name` for the client address (by="ip") or account (by="user"); True if over."""
    who = client_ip(request) if by == "ip" else str(request.user.pk)
    if hit(f"{name}:{by}:{who}", settings.NRMP_RATE_LIMITS[name]):
        logger.warning("Rate limit reached: %s by %s", name, by)
        return True
    return False


def rate_limit(name: str, *, by: str) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    """Limit a view's POSTs per client address (by="ip") or per account (by="user").

    The rate is `settings.NRMP_RATE_LIMITS[name]`. Over the limit the view is not called and the response has
    status 429.
    """

    def decorator(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @functools.wraps(view)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if request.method == "POST" and over_limit(request, name, by=by):
                return too_many_requests(request)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
