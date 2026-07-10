"""Shared test fixtures for the yerba mate reduction service."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest

# ---------------------------------------------------------------------------
# Project root on sys.path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from helpers import make_plan_day as make_plan_day  # noqa: E402

import db  # noqa: E402

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://localhost:5432/yerba_mate_test",
)

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db() -> Generator[None, None, None]:
    """Initialise the test database and truncate tables between tests."""
    db.init_db(_TEST_DATABASE_URL)
    with db._connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE plan_days, actuals")
        conn.commit()
    yield
    db.close_db()
