import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from patentic.report.bundle import LABEL, ReportBundle
from patentic.report.formatters import fmt_confidence, fmt_date, fmt_patent, fmt_score, fmt_status
from tests.graph.helpers import REQUEST
from tests.report.helpers import demo_bundle


def test_bundle_node_writes_json_and_prose_keys(tmp_path: Path) -> None:
    bundle: ReportBundle = demo_bundle(tmp_path)
    assert bundle.label == LABEL
    assert {"executive_summary", "methodology", "commercial", "next_steps"} <= set(bundle.prose)
    assert bundle.run.is_demo
    assert all(c.is_synthetic for c in bundle.candidates)
    assert bundle.flow.expired_in_window == 6
    assert bundle.illustration is not None
    assert bundle.illustration.key == "US-9999902"
    assert len(bundle.candidates) <= REQUEST.max_candidates
    assert "\u2014" not in json.dumps(bundle.prose)


def test_every_cited_evidence_id_has_a_reference(tmp_path: Path) -> None:
    bundle: ReportBundle = demo_bundle(tmp_path)
    refs: set[str] = {r.id for r in bundle.references}
    cited: set[str] = {e for c in bundle.candidates for e in c.evidence_ids}
    assert cited <= refs


def test_bundle_validators_reject_shortlist_not_in_candidates(tmp_path: Path) -> None:
    bundle: ReportBundle = demo_bundle(tmp_path)
    data: dict[str, Any] = bundle.model_dump()
    data["shortlist"] = ["US-1234567"]
    with pytest.raises(ValueError, match="shortlist"):
        ReportBundle.model_validate(data)


def test_bundle_rejects_mixed_synthetic_without_demo(tmp_path: Path) -> None:
    data: dict[str, Any] = demo_bundle(tmp_path).model_dump()
    data["run"]["is_demo"] = False
    with pytest.raises(ValueError, match="synthetic"):
        ReportBundle.model_validate(data)


def test_formatters_are_deterministic() -> None:
    assert fmt_patent("US-8826466") == "US 8,826,466"
    assert fmt_patent("US-RE46721") == "US RE46,721"
    assert fmt_date(date(2026, 9, 9)) == "2026-09-09"
    assert fmt_date(None) == "n/a"
    assert fmt_score(3.456) == "3.5"
    assert fmt_status("expired_nonpayment") == "Expired (nonpayment)"
    assert fmt_status("reinstated") == "Reinstated"
    assert fmt_confidence("very_high") == "very high"
