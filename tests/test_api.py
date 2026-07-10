"""Tests for the read-only HTTP API endpoints in api.py."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

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


class TestHealthz:
    """Tests for GET /healthz."""

    async def test_healthz_requires_no_auth(self, client: TestClient) -> None:
        """Test that the health check responds without a bearer token."""
        response = await client.get("/healthz")

        assert response.status == 200
        assert await response.json() == {"ok": True}


class TestAuthRequired:
    """Tests that every /api/v1 endpoint rejects unauthenticated requests."""

    @pytest.mark.parametrize(
        "path", ["/api/v1/plan", "/api/v1/status", "/api/v1/history"]
    )
    async def test_missing_bearer_returns_401(
        self, client: TestClient, path: str
    ) -> None:
        """Test that requests without an Authorization header get 401."""
        response = await client.get(path)

        assert response.status == 401
        assert await response.json() == {"error": "missing bearer token"}


class TestGetPlan:
    """Tests for GET /api/v1/plan."""

    async def test_returns_full_plan_with_date_range(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test the happy path: plan rows plus starts_on/ends_on bounds."""
        first = date(2026, 7, 1)
        last = date(2026, 7, 2)
        rows = [make_plan_day(first, large=3), make_plan_day(last, large=2)]
        monkeypatch.setattr(db, "get_all_plan_days", lambda: rows)

        response = await client.get("/api/v1/plan", headers=_auth_headers())

        assert response.status == 200
        assert await response.json() == {
            "plan": [
                {"date": "2026-07-01", "small": 0, "large": 3, "total_mg": 450},
                {"date": "2026-07-02", "small": 0, "large": 2, "total_mg": 300},
            ],
            "starts_on": "2026-07-01",
            "ends_on": "2026-07-02",
        }

    async def test_empty_plan_has_null_bounds(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that an empty plan serializes with null starts_on/ends_on."""
        monkeypatch.setattr(db, "get_all_plan_days", list)

        response = await client.get("/api/v1/plan", headers=_auth_headers())

        assert response.status == 200
        assert await response.json() == {
            "plan": [],
            "starts_on": None,
            "ends_on": None,
        }


class TestGetStatus:
    """Tests for GET /api/v1/status."""

    @staticmethod
    def _patch_today(
        monkeypatch: pytest.MonkeyPatch,
        plan: PlanDay | None,
        actual: PlanDay | None,
    ) -> None:
        """Stub the two DB reads used by the status endpoint."""
        monkeypatch.setattr(db, "get_plan_day", lambda _d: plan)
        monkeypatch.setattr(db, "get_actual", lambda _d: actual)

    async def test_under_plan_is_on_track(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test delta_mg and on_track when consumption is under plan."""
        today = date.today()
        self._patch_today(
            monkeypatch,
            plan=make_plan_day(today, large=3),
            actual=make_plan_day(today, large=2),
        )

        response = await client.get("/api/v1/status", headers=_auth_headers())

        assert response.status == 200
        assert await response.json() == {
            "date": today.isoformat(),
            "plan": {"small": 0, "large": 3, "total_mg": 450},
            "actual": {"small": 0, "large": 2, "total_mg": 300},
            "delta_mg": -150,
            "on_track": True,
        }

    async def test_exactly_on_plan_is_on_track(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test the boundary: actual == plan counts as on track."""
        today = date.today()
        self._patch_today(
            monkeypatch,
            plan=make_plan_day(today, small=1, large=1),
            actual=make_plan_day(today, small=1, large=1),
        )

        response = await client.get("/api/v1/status", headers=_auth_headers())

        body = await response.json()
        assert body["delta_mg"] == 0
        assert body["on_track"] is True

    async def test_over_plan_is_off_track(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that exceeding the planned total flips on_track to False."""
        today = date.today()
        self._patch_today(
            monkeypatch,
            plan=make_plan_day(today, small=1),
            actual=make_plan_day(today, large=1),
        )

        response = await client.get("/api/v1/status", headers=_auth_headers())

        body = await response.json()
        assert body["delta_mg"] == 35
        assert body["on_track"] is False

    async def test_no_actual_defaults_to_zero(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a day with no logged actuals reports zero consumption."""
        today = date.today()
        self._patch_today(monkeypatch, plan=make_plan_day(today, large=2), actual=None)

        response = await client.get("/api/v1/status", headers=_auth_headers())

        body = await response.json()
        assert body["actual"] == {"small": 0, "large": 0, "total_mg": 0}
        assert body["delta_mg"] == -300
        assert body["on_track"] is True

    async def test_no_plan_for_today_returns_404(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a missing plan day yields a 404 error body."""
        self._patch_today(monkeypatch, plan=None, actual=None)

        response = await client.get("/api/v1/status", headers=_auth_headers())

        assert response.status == 404
        assert await response.json() == {"error": "no plan for today"}


class TestGetHistory:
    """Tests for GET /api/v1/history."""

    @pytest.mark.parametrize("weeks", ["0", "53", "-1", "not-a-number"])
    async def test_out_of_range_weeks_returns_400(
        self, client: TestClient, weeks: str
    ) -> None:
        """Test that weeks outside 1..52 (or non-integer) get 400."""
        response = await client.get(
            "/api/v1/history",
            params={"weeks": weeks},
            headers=_auth_headers(),
        )

        assert response.status == 400
        assert await response.json() == {
            "error": "weeks must be an integer between 1 and 52"
        }

    async def test_merges_plan_and_actual_rows_by_date(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test the happy path: union of plan/actual dates, sorted ascending."""
        today = date.today()
        both = today - timedelta(days=2)
        plan_only = today - timedelta(days=1)
        seen_ranges: list[tuple[date, date]] = []

        def fake_plan_range(from_date: date, to_date: date) -> list[PlanDay]:
            seen_ranges.append((from_date, to_date))
            return [make_plan_day(both, large=2), make_plan_day(plan_only, large=1)]

        def fake_actuals_range(from_date: date, to_date: date) -> list[PlanDay]:
            return [make_plan_day(both, large=3), make_plan_day(today, small=1)]

        monkeypatch.setattr(db, "get_plan_range", fake_plan_range)
        monkeypatch.setattr(db, "get_actuals_range", fake_actuals_range)

        response = await client.get(
            "/api/v1/history", params={"weeks": "2"}, headers=_auth_headers()
        )

        assert response.status == 200
        assert seen_ranges == [(today - timedelta(weeks=2), today)]
        assert await response.json() == {
            "history": [
                {
                    "date": both.isoformat(),
                    "plan": {"small": 0, "large": 2, "total_mg": 300},
                    "actual": {"small": 0, "large": 3, "total_mg": 450},
                },
                {
                    "date": plan_only.isoformat(),
                    "plan": {"small": 0, "large": 1, "total_mg": 150},
                    "actual": None,
                },
                {
                    "date": today.isoformat(),
                    "plan": None,
                    "actual": {"small": 1, "large": 0, "total_mg": 115},
                },
            ]
        }

    async def test_weeks_defaults_to_four(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that omitting ?weeks= queries the past four weeks."""
        today = date.today()
        seen_ranges: list[tuple[date, date]] = []

        def fake_range(from_date: date, to_date: date) -> list[PlanDay]:
            seen_ranges.append((from_date, to_date))
            return []

        monkeypatch.setattr(db, "get_plan_range", fake_range)
        monkeypatch.setattr(db, "get_actuals_range", fake_range)

        response = await client.get("/api/v1/history", headers=_auth_headers())

        assert response.status == 200
        assert await response.json() == {"history": []}
        assert seen_ranges == [(today - timedelta(weeks=4), today)] * 2
