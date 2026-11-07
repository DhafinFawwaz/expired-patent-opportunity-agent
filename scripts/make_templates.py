"""Regenerate templates/report_template.docx and templates/deck_template.pptx."""

from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from pptx import Presentation
from pptx.util import Inches as PptxInches

from patentic.report.bundle import LABEL
from patentic.report.oxml import add_field

ROOT: Path = Path(__file__).parents[1]


def make_report_template(path: Path) -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Inches(1))
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    disclaimer = doc.styles.add_style("Disclaimer", WD_STYLE_TYPE.PARAGRAPH)
    disclaimer.base_style = normal
    disclaimer.font.italic = True
    disclaimer.font.size = Pt(9)
    disclaimer.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    caption = doc.styles["Caption"]
    caption.font.size = Pt(9)
    header = section.header.paragraphs[0]
    header.text = LABEL
    header.style = disclaimer
    footer = section.footer.paragraphs[0]
    footer.style = disclaimer
    footer.add_run("Page ")
    add_field(footer, "PAGE")
    zoom = doc.settings.element.find(qn("w:zoom"))
    if zoom is not None:
        zoom.set(qn("w:percent"), "100")
    doc.save(str(path))


def make_deck_template(path: Path) -> None:
    deck = Presentation()
    deck.slide_width = PptxInches(13.333)
    deck.slide_height = PptxInches(7.5)
    deck.save(str(path))


if __name__ == "__main__":
    make_report_template(ROOT / "templates" / "report_template.docx")
    make_deck_template(ROOT / "templates" / "deck_template.pptx")
