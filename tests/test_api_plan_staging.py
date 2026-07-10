"""Tests for the staged pending-confirmation plan flow in api.py."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from aiohttp.test_utils import TestClient, TestServer
from helpers import make_plan_day

import api
import db
from auth_middleware import SECRET_ENV_VAR, mint_token

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from planner import PlanDay

TEST_SECRET = "test-shared-secret"
CALLER_ID = "rubotpaul"


@pytest.fixture()
def shared_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set RUBOTPAUL_SHARED_SECRET in the environment for a test."""
    monkeypatch.setenv(SECRET_ENV_VAR, TEST_SECRET)
    return TEST_SECRET


@pytest.fixture()
async def client(shared_secret: str) -> AsyncIterator[TestClient]:
    """Serve the API app and yield a connected test client."""
    test_client = TestClient(TestServer(api.build_app()))
    await test_client.start_server()
    yield test_client
    await test_client.close()


def _auth_headers() -> dict[str, str]:
    """Build an Authorization header with a freshly minted token."""
    return {"Authorization": f"Bearer {mint_token(CALLER_ID)}"}


def _capture_save_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> list[list[PlanDay]]:
    """Stub db.save_plan and record the plans it is called with."""
    calls: list[list[PlanDay]] = []

    def fake_save(plan: list[PlanDay]) -> None:
        calls.append(plan)

    monkeypatch.setattr(db, "save_plan", fake_save)
    return calls


def _stub_generate_plan(
    monkeypatch: pytest.MonkeyPatch, plan: list[PlanDay]
) -> list[dict[str, Any]]:
    """Stub api.generate_plan and record its call keyword arguments."""
    calls: list[dict[str, Any]] = []

    def fake_generate(
        small: int, large: int, start_date: date, *, skip_hold: bool = False
    ) -> list[PlanDay]:
        calls.append(
            {
                "small": small,
                "large": large,
                "start_date": start_date,
                "skip_hold": skip_hold,
            }
        )
        return plan

    monkeypatch.setattr(api, "generate_plan", fake_generate)
    return calls


async def _stage_plan(client: TestClient, body: dict[str, Any] | None = None) -> str:
    """POST /api/v1/plan and return the staged action_id."""
    payload = {"large": 2, "small": 1, "strategy": "replan"} if body is None else body
    response = await client.post("/api/v1/plan", json=payload, headers=_auth_headers())
    assert response.status == 200
    staged = await response.json()
    action_id = staged["action_id"]
    assert isinstance(action_id, str)
    return action_id


class TestPostPlanRequiresAuth:
    """Tests that the staged plan endpoints reject unauthenticated requests."""

    @pytest.mark.parametrize("path", ["/api/v1/plan", "/api/v1/plan/confirm"])
    async def test_missing_bearer_returns_401(
        self, client: TestClient, path: str
    ) -> None:
        """Test that POSTs without an Authorization header get 401."""
        response = await client.post(path, json={})

        assert response.status == 401
        assert await response.json() == {"error": "missing bearer token"}


class TestPostPlan:
    """Tests for POST /api/v1/plan (stage only — never writes)."""

    async def test_returns_pending_and_does_not_execute(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that staging returns pending_confirmation without a DB write."""
        save_calls = _capture_save_plan(monkeypatch)

        response = await client.post(
            "/api/v1/plan",
            json={"large": 2, "small": 1, "strategy": "replan"},
            headers=_auth_headers(),
        )

        assert response.status == 200
        body = await response.json()
        assert body["status"] == "pending_confirmation"
        assert body["kind"] == "plan_create"
        assert body["expires_in"] == api.PLAN_TTL_SECONDS
        assert isinstance(body["action_id"], str) and body["action_id"]
        assert save_calls == []

    async def test_preview_describes_the_staged_plan(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the preview reflects the plan that confirm would write."""
        today = date.today()
        plan = [make_plan_day(today, large=2), make_plan_day(today + timedelta(days=1))]
        _stub_generate_plan(monkeypatch, plan)
        save_calls = _capture_save_plan(monkeypatch)

        response = await client.post(
            "/api/v1/plan",
            json={"large": 2, "small": 0},
            headers=_auth_headers(),
        )

        body = await response.json()
        assert body["preview"] == {
            "large": 2,
            "small": 0,
            "strategy": "replan",
            "days": 2,
            "starts_on": today.isoformat(),
            "ends_on": (today + timedelta(days=1)).isoformat(),
        }
        assert save_calls == []

    async def test_strategy_defaults_to_replan(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that omitting strategy stages a replan."""
        _capture_save_plan(monkeypatch)

        response = await client.post(
            "/api/v1/plan", json={"large": 1, "small": 0}, headers=_auth_headers()
        )

        body = await response.json()
        assert body["preview"]["strategy"] == "replan"

    @pytest.mark.parametrize("strategy", ["yolo", 3, None, ""])
    async def test_bad_strategy_returns_400(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        strategy: object,
    ) -> None:
        """Test that strategies outside replan/catchup are rejected."""
        save_calls = _capture_save_plan(monkeypatch)

        response = await client.post(
            "/api/v1/plan",
            json={"large": 1, "small": 0, "strategy": strategy},
            headers=_auth_headers(),
        )

        assert response.status == 400
        assert await response.json() == {
            "error": "strategy must be 'replan' or 'catchup'"
        }
        assert save_calls == []

    @pytest.mark.parametrize(
        "body", [{"large": -1, "small": 0}, {"large": True}, {"small": "2"}]
    )
    async def test_invalid_counts_return_400(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        body: dict[str, object],
    ) -> None:
        """Test that invalid drink counts are rejected without staging."""
        save_calls = _capture_save_plan(monkeypatch)

        response = await client.post("/api/v1/plan", json=body, headers=_auth_headers())

        assert response.status == 400
        assert await response.json() == {
            "error": "large and small must be non-negative integers"
        }
        assert save_calls == []

    async def test_invalid_json_body_returns_400(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a non-object body is rejected with a clear error."""
        save_calls = _capture_save_plan(monkeypatch)

        response = await client.post(
            "/api/v1/plan",
            data="[]",
            headers={**_auth_headers(), "Content-Type": "application/json"},
        )

        assert response.status == 400
        assert await response.json() == {"error": "request body must be a JSON object"}
        assert save_calls == []


class TestPostPlanConfirm:
    """Tests for POST /api/v1/plan/confirm (executes the staged action)."""

    async def test_confirm_executes_replan_and_writes(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test the happy path: confirm generates the plan and saves it."""
        today = date.today()
        plan = [make_plan_day(today, large=2), make_plan_day(today + timedelta(days=1))]
        generate_calls = _stub_generate_plan(monkeypatch, plan)
        save_calls = _capture_save_plan(monkeypatch)
        action_id = await _stage_plan(
            client, {"large": 2, "small": 1, "strategy": "replan"}
        )
        generate_calls.clear()  # drop the staging preview call

        response = await client.post(
            "/api/v1/plan/confirm",
            json={"action_id": action_id},
            headers=_auth_headers(),
        )

        assert response.status == 200
        assert await response.json() == {
            "status": "executed",
            "action_id": action_id,
            "kind": "plan_create",
            "plan": {
                "days": 2,
                "starts_on": today.isoformat(),
                "ends_on": (today + timedelta(days=1)).isoformat(),
            },
        }
        assert generate_calls == [
            {"small": 1, "large": 2, "start_date": today, "skip_hold": False}
        ]
        assert save_calls == [plan]

    async def test_confirm_executes_catchup_from_tomorrow(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that catchup plans start tomorrow and skip the initial hold."""
        tomorrow = date.today() + timedelta(days=1)
        plan = [make_plan_day(tomorrow, large=1)]
        generate_calls = _stub_generate_plan(monkeypatch, plan)
        save_calls = _capture_save_plan(monkeypatch)
        action_id = await _stage_plan(
            client, {"large": 1, "small": 0, "strategy": "catchup"}
        )
        generate_calls.clear()

        response = await client.post(
            "/api/v1/plan/confirm",
            json={"action_id": action_id},
            headers=_auth_headers(),
        )

        assert response.status == 200
        assert generate_calls == [
            {"small": 0, "large": 1, "start_date": tomorrow, "skip_hold": True}
        ]
        assert save_calls == [plan]

    async def test_unknown_action_id_returns_404(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a never-staged action_id yields 404."""
        save_calls = _capture_save_plan(monkeypatch)

        response = await client.post(
            "/api/v1/plan/confirm",
            json={"action_id": "no-such-action"},
            headers=_auth_headers(),
        )

        assert response.status == 404
        assert await response.json() == {"error": "unknown action_id"}
        assert save_calls == []

    async def test_expired_action_returns_410(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that confirming after the TTL yields 410 and no write."""
        save_calls = _capture_save_plan(monkeypatch)
        action_id = await _stage_plan(client)
        beyond_ttl = datetime.now(tz=UTC) + timedelta(seconds=api.PLAN_TTL_SECONDS + 1)
        monkeypatch.setattr(api, "_utcnow", lambda: beyond_ttl)

        response = await client.post(
            "/api/v1/plan/confirm",
            json={"action_id": action_id},
            headers=_auth_headers(),
        )

        assert response.status == 410
        assert await response.json() == {"error": "action expired"}
        assert save_calls == []

    async def test_double_confirm_returns_409(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a second confirm is rejected and writes exactly once."""
        plan = [make_plan_day(date.today(), large=2)]
        _stub_generate_plan(monkeypatch, plan)
        save_calls = _capture_save_plan(monkeypatch)
        action_id = await _stage_plan(client)

        first = await client.post(
            "/api/v1/plan/confirm",
            json={"action_id": action_id},
            headers=_auth_headers(),
        )
        second = await client.post(
            "/api/v1/plan/confirm",
            json={"action_id": action_id},
            headers=_auth_headers(),
        )

        assert first.status == 200
        assert second.status == 409
        assert await second.json() == {"error": "action already resolved"}
        assert save_calls == [plan]

    async def test_confirm_after_expiry_marks_action_resolved(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that an expired action stays dead: 410 first, then 409."""
        save_calls = _capture_save_plan(monkeypatch)
        action_id = await _stage_plan(client)
        beyond_ttl = datetime.now(tz=UTC) + timedelta(seconds=api.PLAN_TTL_SECONDS + 1)
        monkeypatch.setattr(api, "_utcnow", lambda: beyond_ttl)

        first = await client.post(
            "/api/v1/plan/confirm",
            json={"action_id": action_id},
            headers=_auth_headers(),
        )
        second = await client.post(
            "/api/v1/plan/confirm",
            json={"action_id": action_id},
            headers=_auth_headers(),
        )

        assert first.status == 410
        assert second.status == 409
        assert save_calls == []

    @pytest.mark.parametrize("body", [{}, {"action_id": 3}, {"action_id": ""}])
    async def test_missing_action_id_returns_400(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        body: dict[str, object],
    ) -> None:
        """Test that a missing or non-string action_id is rejected."""
        save_calls = _capture_save_plan(monkeypatch)

        response = await client.post(
            "/api/v1/plan/confirm", json=body, headers=_auth_headers()
        )

        assert response.status == 400
        assert await response.json() == {"error": "action_id must be a string"}
        assert save_calls == []

    async def test_invalid_json_body_returns_400(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a non-object body is rejected with a clear error."""
        save_calls = _capture_save_plan(monkeypatch)

        response = await client.post(
            "/api/v1/plan/confirm",
            data="not json",
            headers={**_auth_headers(), "Content-Type": "application/json"},
        )

        assert response.status == 400
        assert await response.json() == {"error": "request body must be a JSON object"}
        assert save_calls == []
