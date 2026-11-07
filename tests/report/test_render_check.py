import shutil
from pathlib import Path

import pytest

from patentic.report.bundle import ReportBundle
from patentic.report.docx_renderer import render_docx
from patentic.report.validate import pdf_page_count
from tests.report.helpers import TEMPLATES


@pytest.mark.render
def test_docx_renders_to_a_report_length(bundle: ReportBundle, tmp_path: Path) -> None:
    if shutil.which("soffice") is None:
        pytest.skip("LibreOffice is not installed")
    docx: Path = render_docx(bundle, TEMPLATES / "report_template.docx", tmp_path / "report.docx")
    pages: int | None = pdf_page_count(docx)
    assert pages is not None
    assert 6 <= pages <= 14
