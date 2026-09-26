"""Request helpers for security features."""

from django.conf import settings


def client_ip(request) -> str | None:
    """Return the client's IP address when the site runs behind `TRUSTED_PROXY_COUNT` reverse proxies.

    Each proxy appends the address it received the request from to `X-Forwarded-For`. The entry that many places
    from the right was therefore added by our own outermost proxy, and a client cannot forge it by sending its own
    header. Without trusted proxies (local development) the socket address is used. django-axes uses this to count
    failed sign-ins per client.
    """
    count = settings.TRUSTED_PROXY_COUNT
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if count and forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if len(hops) >= count:
            return hops[-count]
    return request.META.get("REMOTE_ADDR")
