from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph


def add_hyperlink(paragraph: Paragraph, url: str, text: str) -> None:
    rel_id: str = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rel_id)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "Hyperlink")
    props.append(style)
    colour = OxmlElement("w:color")
    colour.set(qn("w:val"), "1F3A5F")
    props.append(colour)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    props.append(underline)
    run.append(props)
    content = OxmlElement("w:t")
    content.text = text
    content.set(qn("xml:space"), "preserve")
    run.append(content)
    link.append(run)
    paragraph._p.append(link)  # noqa: SLF001  # python-docx has no hyperlink API


def add_field(paragraph: Paragraph, instruction: str) -> None:
    for kind, text in (
        ("begin", None),
        (None, instruction),
        ("separate", None),
        (None, "1"),
        ("end", None),
    ):
        run = OxmlElement("w:r")
        if kind:
            char = OxmlElement("w:fldChar")
            char.set(qn("w:fldCharType"), kind)
            run.append(char)
        elif text == instruction:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = f" {instruction} "
            run.append(instr)
        else:
            placeholder = OxmlElement("w:t")
            placeholder.text = text
            run.append(placeholder)
        paragraph._p.append(run)  # noqa: SLF001


def shade_header_row(table: Table, fill: str = "D9E2F3") -> None:
    for cell in table.rows[0].cells:
        props = cell._tc.get_or_add_tcPr()  # noqa: SLF001
        shading = OxmlElement("w:shd")
        shading.set(qn("w:val"), "clear")
        shading.set(qn("w:color"), "auto")
        shading.set(qn("w:fill"), fill)
        props.append(shading)


def repeat_header_row(table: Table) -> None:
    props = table.rows[0]._tr.get_or_add_trPr()  # noqa: SLF001
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    props.append(header)


# Schema order: these are the elements that must come after shd and pBdr in w:pPr and w:tcPr.
_AFTER_SHD_P: tuple[str, ...] = (
    "w:tabs",
    "w:suppressAutoHyphens",
    "w:kinsoku",
    "w:wordWrap",
    "w:overflowPunct",
    "w:topLinePunct",
    "w:autoSpaceDE",
    "w:autoSpaceDN",
    "w:bidi",
    "w:adjustRightInd",
    "w:snapToGrid",
    "w:spacing",
    "w:ind",
    "w:contextualSpacing",
    "w:mirrorIndents",
    "w:suppressOverlap",
    "w:jc",
    "w:textDirection",
    "w:textAlignment",
    "w:textboxTightWrap",
    "w:outlineLvl",
    "w:divId",
    "w:cnfStyle",
    "w:rPr",
    "w:sectPr",
    "w:pPrChange",
)
_AFTER_SHD_TC: tuple[str, ...] = (
    "w:noWrap",
    "w:tcMar",
    "w:textDirection",
    "w:tcFitText",
    "w:vAlign",
    "w:hideMark",
    "w:headers",
    "w:cellIns",
    "w:cellDel",
    "w:cellMerge",
    "w:tcPrChange",
)


def _shd(fill: str) -> OxmlElement:  # type: ignore[valid-type]
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), fill)
    return shading


def shade_paragraph(paragraph: Paragraph, fill: str) -> None:
    props = paragraph._p.get_or_add_pPr()  # noqa: SLF001
    props.insert_element_before(_shd(fill), *_AFTER_SHD_P)


def border(
    paragraph: Paragraph, sides: tuple[str, ...], colour: str, eighths: int = 4, space: int = 4
) -> None:
    borders = OxmlElement("w:pBdr")
    for side in ("top", "left", "bottom", "right"):
        if side not in sides:
            continue
        line = OxmlElement(f"w:{side}")
        for key, value in (
            ("val", "single"),
            ("sz", str(eighths)),
            ("space", str(space)),
            ("color", colour),
        ):
            line.set(qn(f"w:{key}"), value)
        borders.append(line)
    props = paragraph._p.get_or_add_pPr()  # noqa: SLF001
    props.insert_element_before(borders, "w:shd", *_AFTER_SHD_P)


def style_cell(cell: _Cell, bottom: str, eighths: int, fill: str | None = None) -> None:
    props = cell._tc.get_or_add_tcPr()  # noqa: SLF001
    borders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        line = OxmlElement(f"w:{side}")
        if side == "bottom":
            line.set(qn("w:val"), "single")
            line.set(qn("w:sz"), str(eighths))
            line.set(qn("w:color"), bottom)
        else:
            line.set(qn("w:val"), "nil")
        borders.append(line)
    props.insert_element_before(borders, "w:shd", *_AFTER_SHD_TC)
    if fill:
        props.insert_element_before(_shd(fill), *_AFTER_SHD_TC)


def full_width(table: Table) -> None:
    props = table._tbl.tblPr  # noqa: SLF001
    for old in props.findall(qn("w:tblW")):
        props.remove(old)
    width = OxmlElement("w:tblW")
    width.set(qn("w:type"), "pct")
    width.set(qn("w:w"), "5000")
    props.insert_element_before(
        width,
        "w:jc",
        "w:tblCellSpacing",
        "w:tblInd",
        "w:tblBorders",
        "w:shd",
        "w:tblLayout",
        "w:tblCellMar",
        "w:tblLook",
        "w:tblCaption",
        "w:tblDescription",
        "w:tblPrChange",
    )
