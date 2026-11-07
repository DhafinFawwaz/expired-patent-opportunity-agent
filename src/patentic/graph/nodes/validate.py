from pathlib import Path
from typing import Final, Literal

from langgraph.types import Command

from patentic.graph.deps import Deps
from patentic.graph.progress import emit
from patentic.graph.state import PipelineState
from patentic.report.bundle import ReportBundle
from patentic.report.validate import ValidationReport, validate_outputs

MAX_ATTEMPTS: Final[int] = 3


class Validate:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> Command[Literal["generate", "__end__"]]:
        bundle: ReportBundle = ReportBundle.model_validate_json(
            Path(state["bundle_path"]).read_text()
        )
        report: ValidationReport = validate_outputs(
            bundle, Path(state["report_path"]), Path(state["deck_path"]), render=self._deps.render
        )
        Path(state["report_path"]).with_name("validation.json").write_text(
            report.model_dump_json(indent=2)
        )
        failed: list[str] = [name for name, ok, _ in report.checks if not ok]
        emit(
            "validation",
            "checked",
            ok=report.ok,
            failed=",".join(failed) or "none",
            pages=report.page_count,
        )
        if report.ok:
            return Command(goto="__end__", update={"validation": report, "stage": "validated"})
        if state.get("generation_attempts", 0) < MAX_ATTEMPTS:
            return Command(goto="generate", update={"validation": report})
        return Command(goto="__end__", update={"validation": report, "stage": "validation_failed"})
