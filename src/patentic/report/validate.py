import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Final

from docx import Document
from pptx import Presentation
from pydantic import BaseModel
from pypdf import PdfReader

from patentic.report.bundle import LABEL, ReportBundle
from patentic.report.docx_renderer import COMPARISON_HEADER, SECTIONS
from patentic.report.formatters import fmt_score, fmt_status

VALIDATOR: Final[Path] = Path(__file__).parents[3] / "tools" / "ooxml" / "validate.py"
MIN_SLIDES: Final[int] = 8
MAX_SLIDES: Final[int] = 10

CandidateFacts = dict[str, tuple[str, str, str]]
Check = tuple[str, bool, str]


class DocFacts(BaseModel):
    candidates: CandidateFacts
    label_locations: list[str]
    slide_count: int | None = None
    section_titles: list[str] = []


class ValidationReport(BaseModel):
    ok: bool
    checks: list[Check]
    page_count: int | None = None


def bundle_facts(bundle: ReportBundle) -> CandidateFacts:
    return {
        c.display: (
            fmt_status(c.status.label),
            fmt_score(c.scores.total if c.scores else None),
            c.recommendation,
        )
        for c in bundle.candidates
    }


def _row_facts(cells: list[str]) -> tuple[str, tuple[str, str, str]]:
    return cells[0], (cells[2], cells[4], cells[5])


def extract_docx_facts(path: Path) -> DocFacts:
    doc = Document(str(path))
    candidates: CandidateFacts = {}
    for table in doc.tables:
        header: tuple[str, ...] = tuple(cell.text for cell in table.rows[0].cells)
        if header != COMPARISON_HEADER:
            continue
        for row in table.rows[1:]:
            key, facts = _row_facts([cell.text for cell in row.cells])
            candidates[key] = facts
    texts: list[str] = [p.text for p in doc.paragraphs]
    locations: list[str] = []
    if LABEL in doc.sections[0].header.paragraphs[0].text:
        locations.append("header")
    if LABEL in texts[:4]:
        locations.append("body")
    last_heading: str = f"10. {SECTIONS[-1]}"
    if last_heading in texts and texts[texts.index(last_heading) + 1] == LABEL:
        locations.append("section10")
    if doc.core_properties.subject == LABEL:
        locations.append("properties")
    titles: list[str] = [
        p.text for p in doc.paragraphs if p.style is not None and p.style.name == "Heading 1"
    ]
    return DocFacts(candidates=candidates, label_locations=locations, section_titles=titles)


def extract_pptx_facts(path: Path) -> DocFacts:
    deck = Presentation(str(path))
    candidates: CandidateFacts = {}
    slide_texts: list[str] = []
    for slide in deck.slides:
        texts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
            if shape.has_table:
                rows = list(shape.table.rows)
                header: tuple[str, ...] = tuple(cell.text for cell in rows[0].cells)
                if header == COMPARISON_HEADER:
                    for row in rows[1:]:
                        key, facts = _row_facts([cell.text for cell in row.cells])
                        candidates[key] = facts
        slide_texts.append("\n".join(texts))
    locations: list[str] = []
    if slide_texts and LABEL in slide_texts[0]:
        locations.append("title")
    if slide_texts and all(LABEL in text for text in slide_texts[1:]):
        locations.append("footers")
    if slide_texts and LABEL in slide_texts[-1]:
        locations.append("last")
    return DocFacts(candidates=candidates, label_locations=locations, slide_count=len(slide_texts))


def ooxml_check(path: Path) -> list[str]:
    done: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [sys.executable, str(VALIDATOR), str(path)],
        cwd=VALIDATOR.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode == 0:
        return []
    return [line for line in (done.stdout + done.stderr).splitlines() if line.strip()][:20]


def pdf_page_count(docx: Path) -> int | None:
    soffice: str | None = shutil.which("soffice")
    if soffice is None:
        return None
    with tempfile.TemporaryDirectory() as work:
        profile: str = Path(work, "profile").as_uri()
        subprocess.run(  # noqa: S603
            [
                soffice,
                f"-env:UserInstallation={profile}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                work,
                str(docx),
            ],
            capture_output=True,
            check=False,
            timeout=180,
        )
        pdf: Path = Path(work) / f"{docx.stem}.pdf"
        return len(PdfReader(str(pdf)).pages) if pdf.exists() else None


def validate_outputs(
    bundle: ReportBundle, docx: Path, pptx: Path, *, render: bool = False
) -> ValidationReport:
    expected: CandidateFacts = bundle_facts(bundle)
    word: DocFacts = extract_docx_facts(docx)
    deck: DocFacts = extract_pptx_facts(pptx)
    checks: list[Check] = [
        ("bundle schema", _revalidates(bundle), ""),
        ("report matches bundle", word.candidates == expected, _diff(expected, word.candidates)),
        ("pptx matches bundle", deck.candidates == expected, _diff(expected, deck.candidates)),
        (
            "report matches deck",
            word.candidates == deck.candidates,
            _diff(word.candidates, deck.candidates),
        ),
        (
            "label in report",
            set(word.label_locations) == {"header", "body", "section10", "properties"},
            ", ".join(word.label_locations),
        ),
        (
            "label in deck",
            set(deck.label_locations) == {"title", "footers", "last"},
            ", ".join(deck.label_locations),
        ),
        (
            "report sections",
            word.section_titles == [f"{i}. {t}" for i, t in enumerate(SECTIONS, start=1)],
            f"{len(word.section_titles)} sections",
        ),
        (
            "slide count",
            deck.slide_count is not None and MIN_SLIDES <= deck.slide_count <= MAX_SLIDES,
            f"{deck.slide_count} slides",
        ),
    ]
    for name, path in (("report schema", docx), ("deck schema", pptx)):
        problems: list[str] = ooxml_check(path)
        checks.append((name, not problems, "; ".join(problems[:3])))
    pages: int | None = pdf_page_count(docx) if render else None
    skipped: str = "render check skipped" + ("" if render else " (not requested)")
    checks.append(("render", True, f"{pages} pages" if pages else skipped))
    return ValidationReport(ok=all(ok for _, ok, _ in checks), checks=checks, page_count=pages)


def _revalidates(bundle: ReportBundle) -> bool:
    try:
        ReportBundle.model_validate(bundle.model_dump())
    except ValueError:
        return False
    return True


def _diff(left: CandidateFacts, right: CandidateFacts) -> str:
    keys: list[str] = sorted(k for k in set(left) | set(right) if left.get(k) != right.get(k))
    return ", ".join(f"{k}: {left.get(k)} vs {right.get(k)}" for k in keys[:3])
