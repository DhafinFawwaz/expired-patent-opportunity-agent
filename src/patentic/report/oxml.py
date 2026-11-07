from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
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
