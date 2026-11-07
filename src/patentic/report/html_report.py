import re
from pathlib import Path
from typing import Final

from patentic.report.bundle import LABEL, ReportBundle
from patentic.report.html_deck import ASSETS, e
from patentic.report.report_content import (
    SECTIONS,
    Block,
    Bullets,
    Heading,
    PageBreak,
    Para,
    Reference,
    Table,
    report_blocks,
    report_meta,
    report_title,
)

_HEADING: Final[re.Pattern[str]] = re.compile(r"(\d+)\. (.+)")


def render_report_html(bundle: ReportBundle, out: Path) -> Path:
    sheets: list[list[str]] = [[_cover(bundle)]]
    for block in report_blocks(bundle):
        if isinstance(block, PageBreak):
            sheets.append([])
        else:
            sheets[-1].append(_block(block))
    running: str = f'<div class="running"><span>{e(LABEL)}</span><span>Run {e(bundle.run.thread_id)}</span></div>'
    pages: str = "\n".join(
        f'<article class="sheet">{running}{"".join(parts)}</article>' for parts in sheets
    )
    toc: str = "".join(
        f'<li><a href="#s{n}"><span class="n">{n}</span>{e(title)}</a></li>'
        for n, title in enumerate(SECTIONS, start=1)
    )
    parts: dict[str, str] = {
        "title": e(report_title(bundle)),
        "css": (ASSETS / "report.css").read_text(),
        "toc": toc,
        "pages": pages,
    }
    page: str = re.sub(r"\{(title|css|toc|pages)\}", lambda m: parts[m.group(1)], _PAGE)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    return out


def _cover(bundle: ReportBundle) -> str:
    return (
        f'<div class="cover"><h1 class="title">{e(report_title(bundle))}</h1>'
        f"<p>{e(report_meta(bundle))}</p></div>"
        f'<p class="disclaimer label">{e(LABEL)}</p>'
    )


def _block(block: Block) -> str:
    if isinstance(block, Heading):
        return _heading(block)
    if isinstance(block, Para):
        css: str = "" if block.kind == "body" else f' class="{block.kind}"'
        if block.text == LABEL:
            css = ' class="disclaimer label"'
        return f"<p{css}>{e(block.text)}</p>"
    if isinstance(block, Bullets):
        if not block.items:
            return ""
        return "<ul>" + "".join(f"<li>{e(item)}</li>" for item in block.items) + "</ul>"
    if isinstance(block, Table):
        return _table(block)
    if isinstance(block, Reference):
        return _reference(block)
    return ""


def _heading(block: Heading) -> str:
    if block.level != 1:
        return f"<h2>{e(block.text)}</h2>"
    match: re.Match[str] | None = _HEADING.fullmatch(block.text)
    if match is None:
        return f"<h1>{e(block.text)}</h1>"
    number, title = match.groups()
    return f'<h1 id="s{number}"><span class="num">{number}.</span> {e(title)}</h1>'


def _table(block: Table) -> str:
    css: str = ' class="comparison"' if block.role == "comparison" else ""
    head: str = "".join(f"<th>{e(h)}</th>" for h in block.header)
    rows: str = "".join(
        f"<tr{' class="shortlist"' if i in block.highlight else ''}>"
        + "".join(f"<td>{e(cell)}</td>" for cell in row)
        + "</tr>"
        for i, row in enumerate(block.rows)
    )
    return f"<table{css}><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"


def _reference(ref: Reference) -> str:
    link: str = f'<a href="{e(ref.url)}">{e(ref.url)}</a>' if ref.url.startswith("http") else ""
    return f'<p class="ref">[{ref.number}] {e(ref.title)}. Retrieved {e(ref.retrieved)}. {link}</p>'


_PAGE: Final[str] = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>
<nav class="toc" aria-label="Sections"><h2>Contents</h2><ol>{toc}</ol></nav>
<main>
{pages}
</main>
</body>
</html>
"""
