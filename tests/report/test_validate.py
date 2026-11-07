from pathlib import Path

import pytest
from pptx import Presentation

from patentic.report.bundle import ReportBundle
from patentic.report.docx_renderer import render_docx
from patentic.report.pptx_renderer import render_pptx
from patentic.report.validate import (
    DocFacts,
    ValidationReport,
    extract_docx_facts,
    extract_pptx_facts,
    ooxml_check,
    validate_outputs,
)
from tests.report.helpers import TEMPLATES


@pytest.fixture(scope="module")
def files(bundle: ReportBundle, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    folder: Path = tmp_path_factory.mktemp("out")
    docx: Path = render_docx(bundle, TEMPLATES / "report_template.docx", folder / "report.docx")
    pptx: Path = render_pptx(bundle, TEMPLATES / "deck_template.pptx", folder / "deck.pptx")
    return docx, pptx


def test_validate_passes_on_consistent_files(
    bundle: ReportBundle, files: tuple[Path, Path]
) -> None:
    report: ValidationReport = validate_outputs(bundle, *files)
    failed: list[str] = [f"{name}: {detail}" for name, ok, detail in report.checks if not ok]
    assert report.ok, failed


def test_extracted_facts_agree(files: tuple[Path, Path]) -> None:
    docx_facts: DocFacts = extract_docx_facts(files[0])
    pptx_facts: DocFacts = extract_pptx_facts(files[1])
    assert docx_facts.candidates == pptx_facts.candidates
    assert set(docx_facts.label_locations) == {"header", "body", "section10", "properties"}
    assert set(pptx_facts.label_locations) == {"title", "footers", "last"}
    assert pptx_facts.slide_count == 9


def test_validate_fails_when_pptx_score_differs(
    bundle: ReportBundle, files: tuple[Path, Path], tmp_path: Path
) -> None:
    deck = Presentation(str(files[1]))
    table = next(shape.table for slide in deck.slides for shape in slide.shapes if shape.has_table)
    table.cell(1, 4).text = "9.9"
    tampered: Path = tmp_path / "tampered.pptx"
    deck.save(str(tampered))
    report: ValidationReport = validate_outputs(bundle, files[0], tampered)
    assert not report.ok
    assert any(name == "pptx matches bundle" and not ok for name, ok, _ in report.checks)


def test_validate_fails_when_label_missing(bundle: ReportBundle, tmp_path: Path) -> None:
    unlabeled: ReportBundle = bundle.model_copy(update={"limitations": bundle.limitations})
    docx: Path = render_docx(unlabeled, TEMPLATES / "report_template.docx", tmp_path / "r.docx")
    from docx import Document

    doc = Document(str(docx))
    doc.sections[0].header.paragraphs[0].text = "Draft"
    doc.save(str(docx))
    pptx: Path = render_pptx(bundle, TEMPLATES / "deck_template.pptx", tmp_path / "d.pptx")
    report: ValidationReport = validate_outputs(bundle, docx, pptx)
    assert any(name == "label in report" and not ok for name, ok, _ in report.checks)


def test_ooxml_check_passes_generated_files(files: tuple[Path, Path]) -> None:
    assert ooxml_check(files[0]) == []
    assert ooxml_check(files[1]) == []
