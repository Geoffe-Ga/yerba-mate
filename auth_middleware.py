"""Shared HMAC bearer auth for RubotPaul-callable services.

Vendored from the RubotPaul migration kit (``shared/auth_middleware.py``).
It's deliberately small and dependency-free (stdlib only, aiohttp imported
lazily) so copy-paste is the right move; resist the urge to package it.
The unused Flask and FastAPI integrations were dropped for this repo.

Usage (aiohttp):

    from auth_middleware import aiohttp_auth_middleware

    app = web.Application(middlewares=[aiohttp_auth_middleware])

Token format: "<caller_id>.<timestamp>.<hmac_hex>"
HMAC = HMAC-SHA256(SHARED_SECRET, f"{caller_id}.{timestamp}").hexdigest()
TTL: tokens older than MAX_TOKEN_AGE_SECONDS are rejected.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiohttp import web

    Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

LOG = logging.getLogger("auth")

MAX_TOKEN_AGE_SECONDS: Final[int] = 300  # 5 minutes — backward window
MAX_TOKEN_FUTURE_SKEW_SECONDS: Final[int] = 30  # forward clock skew tolerance
SECRET_ENV_VAR: Final[str] = "RUBOTPAUL_SHARED_SECRET"


class AuthError(Exception):
    """Raised when bearer token is missing or invalid.

    Attributes:
        reason: Human-readable failure reason.
        status: HTTP status code to respond with.
    """

    def __init__(self, reason: str, status: int = 401) -> None:
        """Initialize the error.

        Args:
            reason: Human-readable failure reason.
            status: HTTP status code to respond with. Defaults to 401.
        """
        super().__init__(reason)
        self.reason = reason
        self.status = status


def _shared_secret() -> bytes:
    """Return the shared secret from the environment as bytes.

    Returns:
        The UTF-8 encoded shared secret.

    Raises:
        RuntimeError: If RUBOTPAUL_SHARED_SECRET is not set.
    """
    secret = os.environ.get(SECRET_ENV_VAR)
    if not secret:
        # Fail loud at startup, not at first request
        msg = f"{SECRET_ENV_VAR} not set; refusing to start auth-protected service"
        raise RuntimeError(msg)
    return secret.encode()


def _verify_token(token: str, *, now: float | None = None) -> str:
    """Return caller_id if token valid, else raise AuthError.

    Args:
        token: Bearer token in "<caller_id>.<timestamp>.<hmac_hex>" format.
        now: Override for the current UNIX time; defaults to time.time().

    Returns:
        The caller_id embedded in the token.

    Raises:
        AuthError: If the token is malformed, expired, from the future,
            or carries a bad signature.
        RuntimeError: If RUBOTPAUL_SHARED_SECRET is not set.
    """
    now = now if now is not None else time.time()
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("malformed token")
    caller_id, ts_str, sig = parts
    try:
        ts = int(ts_str)
    except ValueError as exc:
        raise AuthError("malformed timestamp") from exc

    # Asymmetric: reject expired tokens, tolerate small forward clock skew only.
    # Using abs() here would let an attacker with a fast clock mint long-lived tokens.
    if now - ts > MAX_TOKEN_AGE_SECONDS:
        raise AuthError("token expired")
    if ts - now > MAX_TOKEN_FUTURE_SKEW_SECONDS:
        raise AuthError("token from future")

    expected = hmac.new(
        _shared_secret(),
        f"{caller_id}.{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise AuthError("bad signature")

    return caller_id


def mint_token(caller_id: str, *, now: float | None = None) -> str:
    """Generate a token. Used by RubotPaul-side client code.

    Args:
        caller_id: Identifier of the calling service.
        now: Override for the current UNIX time; defaults to time.time().

    Returns:
        A bearer token in "<caller_id>.<timestamp>.<hmac_hex>" format.

    Raises:
        RuntimeError: If RUBOTPAUL_SHARED_SECRET is not set.
    """
    ts = int(now if now is not None else time.time())
    sig = hmac.new(
        _shared_secret(),
        f"{caller_id}.{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{caller_id}.{ts}.{sig}"


# ---- aiohttp integration --------------------------------------------------


async def aiohttp_auth_middleware(
    app: web.Application | None, handler: Handler
) -> Handler:
    """aiohttp middleware factory. Use with web.Application(middlewares=[...]).

    Args:
        app: The aiohttp application (unused, required by the middleware API).
        handler: The downstream request handler to wrap.

    Returns:
        A handler that enforces bearer auth before delegating to ``handler``.
    """
    from aiohttp import web

    async def middleware(request: web.Request) -> web.StreamResponse:
        """Validate the bearer token, then delegate to the wrapped handler.

        Args:
            request: The incoming HTTP request.

        Returns:
            A 401 JSON error response on auth failure, otherwise the
            wrapped handler's response with request["caller_id"] set.
        """
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return web.json_response({"error": "missing bearer token"}, status=401)
        token = header[len("Bearer ") :]
        try:
            caller_id = _verify_token(token)
        except AuthError as exc:
            return web.json_response({"error": exc.reason}, status=exc.status)
        request["caller_id"] = caller_id
        return await handler(request)

    return middleware
