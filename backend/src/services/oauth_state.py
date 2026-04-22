"""Short-lived state-token store for OAuth CSRF protection.

Every OAuth flow (Google, LinkedIn) generates a random state token at the
/auth/<provider> start endpoint and attaches it to the provider URL.
When the provider redirects back to /auth/<provider>/callback, the state
query param must match a value we previously issued AND be unexpired.

Without this, an attacker can intercept their own valid `code` from
Google, craft a callback URL with that code, trick the victim's browser
into visiting it, and the server treats the callback as if the victim
initiated the flow. The victim ends up logged in as the attacker's
Google identity and unknowingly feeds their data into the attacker's
Azens account — classic OAuth login-CSRF.

Storage: in-memory. Acceptable because:
  - Single-worker uvicorn (multi-worker: swap to Redis).
  - Auth endpoints are rate-limited (store can't grow unboundedly).
  - State is purely ephemeral — losing the dict on restart only means
    any in-flight OAuth flows need to be restarted (browser shows an
    "oauth_failed" redirect). Not a data issue.

When you scale horizontally, swap this module's storage for Redis with
`SETEX` + `GETDEL`. The function interface stays identical.
"""

from __future__ import annotations

import secrets
import time
from threading import Lock

_STATE_STORE: dict[str, float] = {}
_LOCK = Lock()

# How long the user has between hitting "Sign in with Google" and
# approving on Google's screen. 10 min is generous — covers slow users,
# two-factor on Google, network blips. Expired states are rejected.
STATE_TTL_SECONDS = 600


def create_state() -> str:
    """Generate a new state token, store it with expiry, return it.

    Opportunistically sweeps expired entries so the dict doesn't grow
    forever under high signup traffic. Cheap: O(n) over currently-valid
    entries, which stays small given the TTL + rate limits on the
    start endpoints.
    """
    token = secrets.token_urlsafe(32)
    now = time.time()
    with _LOCK:
        # Drop expired entries on each write. Avoids needing a separate
        # janitor task for a tiny ephemeral dict.
        for expired_token in [k for k, v in _STATE_STORE.items() if v < now]:
            _STATE_STORE.pop(expired_token, None)
        _STATE_STORE[token] = now + STATE_TTL_SECONDS
    return token


def consume_state(token: str | None) -> bool:
    """Atomically look up and remove a state token.

    Returns True only if the token was present and unexpired. After this
    call the token is gone from the store — attempting to reuse the same
    state in a second callback will return False. Single-use is essential
    for CSRF protection; without it, a leaked state would remain valid
    for the entire TTL window.
    """
    if not token:
        return False
    with _LOCK:
        expiry = _STATE_STORE.pop(token, None)
    if expiry is None:
        return False
    return expiry > time.time()
