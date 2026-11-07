from pathlib import Path

from typing_extensions import TypedDict

from patentic.graph.deps import Deps
from patentic.graph.progress import emit
from patentic.graph.state import PipelineState
from patentic.report.bundle import ReportBundle
from patentic.report.docx_renderer import render_docx
from patentic.report.pptx_renderer import render_pptx


class GenerateUpdate(TypedDict, total=False):
    stage: str
    report_path: str
    deck_path: str
    generation_attempts: int


class Generate:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState) -> GenerateUpdate:
        bundle_path: Path = Path(state["bundle_path"])
        bundle: ReportBundle = ReportBundle.model_validate_json(bundle_path.read_text())
        templates: Path = self._deps.settings.patentic_templates_dir
        report: Path = render_docx(
            bundle, templates / "report_template.docx", bundle_path.parent / "report.docx"
        )
        deck: Path = render_pptx(
            bundle, templates / "deck_template.pptx", bundle_path.parent / "deck.pptx"
        )
        attempts: int = state.get("generation_attempts", 0) + 1
        emit("generation", "files_written", report=report.name, deck=deck.name, attempt=attempts)
        return {
            "stage": "generation",
            "report_path": str(report),
            "deck_path": str(deck),
            "generation_attempts": attempts,
        }
