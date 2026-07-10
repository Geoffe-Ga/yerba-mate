"""Tests for the vendored auth_middleware module."""

from __future__ import annotations

import json
import time

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from auth_middleware import (
    MAX_TOKEN_AGE_SECONDS,
    MAX_TOKEN_FUTURE_SKEW_SECONDS,
    SECRET_ENV_VAR,
    AuthError,
    _verify_token,
    aiohttp_auth_middleware,
    mint_token,
)

TEST_SECRET = "test-shared-secret"
CALLER_ID = "rubotpaul"


@pytest.fixture()
def shared_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set RUBOTPAUL_SHARED_SECRET in the environment for a test."""
    monkeypatch.setenv(SECRET_ENV_VAR, TEST_SECRET)
    return TEST_SECRET


class TestMintToken:
    """Tests for the mint_token function."""

    def test_token_has_three_dot_separated_parts(self, shared_secret: str) -> None:
        """Test that minted tokens follow the <caller>.<ts>.<sig> format."""
        token = mint_token(CALLER_ID)

        caller_id, ts_str, sig = token.split(".")
        assert caller_id == CALLER_ID
        assert ts_str.isdigit()
        assert len(sig) == 64  # SHA-256 hexdigest length

    def test_uses_current_time_by_default(self, shared_secret: str) -> None:
        """Test that mint_token defaults to the current wall clock."""
        before = int(time.time())
        token = mint_token(CALLER_ID)
        after = int(time.time())

        ts = int(token.split(".")[1])
        assert before <= ts <= after

    def test_missing_shared_secret_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that minting without RUBOTPAUL_SHARED_SECRET raises RuntimeError."""
        monkeypatch.delenv(SECRET_ENV_VAR, raising=False)

        with pytest.raises(RuntimeError, match=SECRET_ENV_VAR):
            mint_token(CALLER_ID)


class TestVerifyToken:
    """Tests for the _verify_token function."""

    def test_valid_token_round_trip(self, shared_secret: str) -> None:
        """Test that a freshly minted token verifies to its caller_id."""
        token = mint_token(CALLER_ID)

        assert _verify_token(token) == CALLER_ID

    def test_valid_token_round_trip_with_explicit_now(self, shared_secret: str) -> None:
        """Test round-trip with an injected clock on both mint and verify."""
        now = 1_700_000_000.0
        token = mint_token(CALLER_ID, now=now)

        assert _verify_token(token, now=now) == CALLER_ID

    def test_token_at_max_age_is_accepted(self, shared_secret: str) -> None:
        """Test that a token exactly MAX_TOKEN_AGE_SECONDS old still verifies."""
        now = 1_700_000_000.0
        token = mint_token(CALLER_ID, now=now)

        caller = _verify_token(token, now=now + MAX_TOKEN_AGE_SECONDS)

        assert caller == CALLER_ID

    def test_expired_token_rejected(self, shared_secret: str) -> None:
        """Test that a token older than MAX_TOKEN_AGE_SECONDS is rejected."""
        now = 1_700_000_000.0
        token = mint_token(CALLER_ID, now=now)

        with pytest.raises(AuthError, match="token expired"):
            _verify_token(token, now=now + MAX_TOKEN_AGE_SECONDS + 1)

    def test_future_token_within_skew_is_accepted(self, shared_secret: str) -> None:
        """Test that a token up to 30s in the future is tolerated."""
        now = 1_700_000_000.0
        token = mint_token(CALLER_ID, now=now + MAX_TOKEN_FUTURE_SKEW_SECONDS)

        assert _verify_token(token, now=now) == CALLER_ID

    def test_future_token_beyond_skew_rejected(self, shared_secret: str) -> None:
        """Test that a token more than 30s in the future is rejected."""
        now = 1_700_000_000.0
        token = mint_token(CALLER_ID, now=now + MAX_TOKEN_FUTURE_SKEW_SECONDS + 1)

        with pytest.raises(AuthError, match="token from future"):
            _verify_token(token, now=now)

    def test_malformed_token_rejected(self, shared_secret: str) -> None:
        """Test that a token without three parts is rejected."""
        with pytest.raises(AuthError, match="malformed token"):
            _verify_token("not-a-token")

    def test_malformed_token_too_many_parts_rejected(self, shared_secret: str) -> None:
        """Test that a token with four parts is rejected."""
        with pytest.raises(AuthError, match="malformed token"):
            _verify_token("a.b.c.d")

    def test_malformed_timestamp_rejected(self, shared_secret: str) -> None:
        """Test that a non-integer timestamp is rejected."""
        with pytest.raises(AuthError, match="malformed timestamp"):
            _verify_token(f"{CALLER_ID}.not-a-number.deadbeef")

    def test_bad_signature_rejected(self, shared_secret: str) -> None:
        """Test that a token with a tampered signature is rejected."""
        token = mint_token(CALLER_ID)
        caller_id, ts_str, sig = token.split(".")
        tampered = f"{caller_id}.{ts_str}.{'0' * len(sig)}"

        with pytest.raises(AuthError, match="bad signature"):
            _verify_token(tampered)

    def test_tampered_caller_id_rejected(self, shared_secret: str) -> None:
        """Test that changing the caller_id invalidates the signature."""
        token = mint_token(CALLER_ID)
        _, ts_str, sig = token.split(".")

        with pytest.raises(AuthError, match="bad signature"):
            _verify_token(f"impostor.{ts_str}.{sig}")

    def test_missing_shared_secret_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that verifying without RUBOTPAUL_SHARED_SECRET raises RuntimeError."""
        monkeypatch.setenv(SECRET_ENV_VAR, TEST_SECRET)
        token = mint_token(CALLER_ID)
        monkeypatch.delenv(SECRET_ENV_VAR)

        with pytest.raises(RuntimeError, match=SECRET_ENV_VAR):
            _verify_token(token)


class TestAuthError:
    """Tests for the AuthError exception."""

    def test_defaults_to_status_401(self) -> None:
        """Test that AuthError carries a 401 status by default."""
        error = AuthError("bad signature")

        assert error.reason == "bad signature"
        assert error.status == 401

    def test_custom_status(self) -> None:
        """Test that AuthError accepts a custom status code."""
        error = AuthError("forbidden", status=403)

        assert error.status == 403


def _make_request(headers: dict[str, str]) -> web.Request:
    """Build a real aiohttp request for middleware tests.

    Args:
        headers: HTTP headers to attach to the request.

    Returns:
        A mocked-transport ``web.Request`` suitable for calling handlers.
    """
    return make_mocked_request("GET", "/", headers=headers)


def _body_text(response: web.StreamResponse) -> str:
    """Narrow a middleware response to ``web.Response`` and return its body.

    Args:
        response: The response returned by the middleware under test.

    Returns:
        The response body decoded as text.
    """
    assert isinstance(response, web.Response)
    assert response.text is not None
    return response.text


class TestAiohttpAuthMiddleware:
    """Tests for the aiohttp middleware factory."""

    @staticmethod
    async def _handler(request: web.Request) -> web.StreamResponse:
        """Echo the authenticated caller_id back in the response body."""
        return web.Response(text=f"hello {request['caller_id']}")

    async def test_valid_token_reaches_handler(self, shared_secret: str) -> None:
        """Test that a valid bearer token passes through to the handler."""
        middleware = await aiohttp_auth_middleware(None, self._handler)
        request = _make_request({"Authorization": f"Bearer {mint_token(CALLER_ID)}"})

        response = await middleware(request)

        assert response.status == 200
        assert _body_text(response) == f"hello {CALLER_ID}"
        assert request["caller_id"] == CALLER_ID

    async def test_missing_header_returns_401(self, shared_secret: str) -> None:
        """Test that a request without an Authorization header gets 401."""
        middleware = await aiohttp_auth_middleware(None, self._handler)
        request = _make_request({})

        response = await middleware(request)

        assert response.status == 401
        assert json.loads(_body_text(response)) == {"error": "missing bearer token"}

    async def test_non_bearer_header_returns_401(self, shared_secret: str) -> None:
        """Test that a non-Bearer Authorization scheme gets 401."""
        middleware = await aiohttp_auth_middleware(None, self._handler)
        request = _make_request({"Authorization": "Basic dXNlcjpwYXNz"})

        response = await middleware(request)

        assert response.status == 401

    async def test_invalid_token_returns_401_with_reason(
        self, shared_secret: str
    ) -> None:
        """Test that an invalid token yields 401 with the failure reason."""
        middleware = await aiohttp_auth_middleware(None, self._handler)
        request = _make_request({"Authorization": "Bearer garbage"})

        response = await middleware(request)

        assert response.status == 401
        assert json.loads(_body_text(response)) == {"error": "malformed token"}

    async def test_expired_token_returns_401(self, shared_secret: str) -> None:
        """Test that an expired token is rejected with 401 at the HTTP layer."""
        stale = mint_token(CALLER_ID, now=time.time() - MAX_TOKEN_AGE_SECONDS - 60)
        middleware = await aiohttp_auth_middleware(None, self._handler)
        request = _make_request({"Authorization": f"Bearer {stale}"})

        response = await middleware(request)

        assert response.status == 401
        assert json.loads(_body_text(response)) == {"error": "token expired"}
