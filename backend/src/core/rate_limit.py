"""Shared rate-limiter instance.

Lives in its own module so route files can import the decorator without
creating a circular dependency with main.py (which owns the app and
registers the exception handler).

Storage: in-memory. Fine for single-worker dev and single-instance
production. For multi-worker uvicorn or horizontal scaling, swap the
storage_uri to Redis (slowapi reads SLOWAPI_STORAGE_URI or accepts it
as a constructor arg — one line change):

    limiter = Limiter(key_func=get_remote_address, storage_uri='redis://...')

Until then, limits reset when the container restarts. Attackers don't
know when we restart, so this is acceptable for launch-day traffic.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# `get_remote_address` reads the client IP from the request. Behind a
# reverse proxy (Cloudflare, nginx), make sure uvicorn is started with
# --proxy-headers so the X-Forwarded-For header is honoured — otherwise
# every request appears to come from the proxy's IP and rate-limits
# become global rather than per-user.
limiter = Limiter(key_func=get_remote_address)
