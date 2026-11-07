"""Regenerate templates/report_template.docx and templates/deck_template.pptx."""

from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from pptx import Presentation
from pptx.util import Inches as PptxInches

from patentic.report.bundle import LABEL
from patentic.report.oxml import add_field

ROOT: Path = Path(__file__).parents[1]


def _font(style: object, size: float, colour: RGBColor, *, bold: bool = False) -> None:
    font = style.font  # type: ignore[attr-defined]
    font.name = "Arial"
    font.size = Pt(size)
    font.bold = bold
    font.italic = False
    font.color.rgb = colour
    rpr = style.element.get_or_add_rPr()  # type: ignore[attr-defined]
    fonts = rpr.get_or_add_rFonts()
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), "Arial")
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        fonts.attrib.pop(qn(attr), None)


INK = RGBColor(0x17, 0x20, 0x2B)
MUTED = RGBColor(0x5B, 0x65, 0x73)
NAVY = RGBColor(0x1F, 0x3A, 0x5F)
AMBER = RGBColor(0xA8, 0x5D, 0x0A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def make_report_template(path: Path) -> None:
    # Mirrors assets/report.css: Arial, the deck palette, Letter with 0.85 in sides.
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.left_margin = section.right_margin = Inches(0.85)
    section.top_margin = section.bottom_margin = Inches(0.8)
    section.header_distance = section.footer_distance = Inches(0.4)
    styles = doc.styles
    normal = styles["Normal"]
    _font(normal, 10.5, INK)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.2
    _font(styles["Title"], 22, WHITE, bold=True)
    styles["Title"].paragraph_format.space_after = Pt(0)
    title_props = styles["Title"].element.pPr
    if title_props is not None:
        for line in title_props.findall(qn("w:pBdr")):
            title_props.remove(line)
    for name, size, before, after in (("Heading 1", 15.5, 20, 8), ("Heading 2", 11.5, 14, 5)):
        heading = styles[name]
        _font(heading, size, INK, bold=True)
        heading.paragraph_format.space_before = Pt(before)
        heading.paragraph_format.space_after = Pt(after)
        heading.paragraph_format.keep_with_next = True
    _font(styles["Caption"], 9, MUTED, bold=True)
    styles["Caption"].paragraph_format.space_before = Pt(8)
    _font(styles["List Bullet"], 10.5, INK)
    styles["List Bullet"].paragraph_format.space_after = Pt(4)
    disclaimer = styles.add_style("Disclaimer", WD_STYLE_TYPE.PARAGRAPH)
    disclaimer.base_style = normal
    _font(disclaimer, 9.5, MUTED)
    disclaimer.font.italic = True
    label = styles.add_style("Label", WD_STYLE_TYPE.PARAGRAPH)
    label.base_style = normal
    _font(label, 10, NAVY, bold=True)
    label.paragraph_format.space_before = Pt(10)
    label.paragraph_format.space_after = Pt(12)
    banner = styles.add_style("Banner", WD_STYLE_TYPE.PARAGRAPH)
    banner.base_style = normal
    _font(banner, 9.5, AMBER, bold=True)
    banner.paragraph_format.space_before = Pt(10)
    meta = styles.add_style("Cover Meta", WD_STYLE_TYPE.PARAGRAPH)
    meta.base_style = normal
    _font(meta, 10.5, RGBColor(0xD3, 0xDA, 0xE3))
    meta.paragraph_format.space_after = Pt(0)
    running = styles.add_style("Running", WD_STYLE_TYPE.PARAGRAPH)
    running.base_style = normal
    _font(running, 8, MUTED)
    running.paragraph_format.space_after = Pt(0)
    usable = section.page_width - section.left_margin - section.right_margin
    header = section.header.paragraphs[0]
    header.text = LABEL
    header.style = running
    header.paragraph_format.tab_stops.add_tab_stop(usable, WD_TAB_ALIGNMENT.RIGHT)
    footer = section.footer.paragraphs[0]
    footer.style = running
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
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
