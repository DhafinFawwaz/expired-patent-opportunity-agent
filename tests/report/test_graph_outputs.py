from pathlib import Path
from typing import Any

import pytest
from langgraph.types import Command

from patentic.graph.deps import Deps
from patentic.graph.nodes import validate as validate_node
from patentic.report.bundle import ReportBundle
from patentic.report.validate import ValidationReport
from tests.graph.helpers import REQUEST, compile_graph, make_deps, plan_replies, run_until_interrupt
from tests.llm.fakes import scripted
from tests.report.helpers import CONFIG, FIXTURES


def finished_run(tmp_path: Path) -> dict[str, Any]:
    deps: Deps = make_deps(tmp_path, tools=scripted(*plan_replies(1)))
    settings = deps.settings.model_copy(update={"patentic_outputs_dir": tmp_path / "outputs"})
    deps = Deps(**{**deps.__dict__, "fixtures": tuple(FIXTURES), "settings": settings})
    graph = compile_graph(deps)
    run_until_interrupt(graph, {"request": REQUEST})
    run_until_interrupt(graph, Command(resume={"action": "approve"}))
    run_until_interrupt(graph, Command(resume={"action": "accept"}))
    values: dict[str, Any] = graph.get_state(CONFIG).values
    return values


def test_graph_writes_valid_report_and_deck(tmp_path: Path) -> None:
    values: dict[str, Any] = finished_run(tmp_path)
    assert Path(values["report_path"]).exists()
    assert Path(values["deck_path"]).exists()
    assert values["validation"].ok, values["validation"].checks
    assert values["stage"] == "validated"
    assert (Path(values["report_path"]).parent / "validation.json").exists()
    names: list[str] = [check[0] for check in values["validation"].checks]
    assert "html matches bundle" in names
    assert "report html matches bundle" in names
    assert (Path(values["report_path"]).parent / "report.html").exists()
    assert (Path(values["deck_path"]).parent / "deck.html").exists()


def test_graph_validation_failure_routes_back_twice_then_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(
        bundle: ReportBundle,
        docx: Path,
        pptx: Path,
        html: Path | None = None,
        report_html: Path | None = None,
        *,
        render: bool = False,
    ) -> ValidationReport:
        return ValidationReport(ok=False, checks=[("forced", False, "test")])

    monkeypatch.setattr(validate_node, "validate_outputs", failing)
    values: dict[str, Any] = finished_run(tmp_path)
    assert values["generation_attempts"] == 3
    assert values["stage"] == "validation_failed"
