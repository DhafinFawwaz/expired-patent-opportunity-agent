import logging

import pytest
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from patentic.graph.state import ReviewDecision
from patentic.report.validate import ValidationReport
from patentic.runner import checkpoint_serde


def test_state_models_round_trip_without_warnings(caplog: pytest.LogCaptureFixture) -> None:
    serde: JsonPlusSerializer = checkpoint_serde()
    report: ValidationReport = ValidationReport(ok=True, checks=[("render", True, "")])
    review: ReviewDecision = ReviewDecision(action="accept")
    with caplog.at_level(logging.WARNING):
        loaded: object = serde.loads_typed(serde.dumps_typed({"v": report, "r": review}))
    assert loaded == {"v": report, "r": review}
    assert "unregistered" not in caplog.text
