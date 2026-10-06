"""Keeps the frontend's test fixture identical to what the real API produces.

The frontend tests load frontend/src/test/fixtures/financials_example.json.
This test regenerates that response from the fictional fixture company and
fails if the committed file differs, so a backend change can't silently
break the frontend's assumptions. To refresh the file after an intended change:

    FSA_UPDATE_FIXTURES=1 uv run pytest tests/api/test_frontend_contract.py
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from test_api import example_history

from fsa.api.presenter import present_financials

FRONTEND_FIXTURE = (
    Path(__file__).parents[2] / "frontend" / "src" / "test" / "fixtures" / "financials_example.json"
)
FIXED_TIME = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def expected_fixture() -> str:
    response = present_financials(example_history(), retrieved_at=FIXED_TIME)
    return json.dumps(response.model_dump(mode="json"), indent=2) + "\n"


def test_frontend_fixture_matches_api() -> None:
    expected = expected_fixture()
    if os.environ.get("FSA_UPDATE_FIXTURES") == "1":
        FRONTEND_FIXTURE.write_text(expected)
    assert FRONTEND_FIXTURE.read_text() == expected, (
        "Frontend fixture is out of date. Run: "
        "FSA_UPDATE_FIXTURES=1 uv run pytest tests/api/test_frontend_contract.py"
    )
