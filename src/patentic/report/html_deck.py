import re
from collections.abc import Callable, Sequence
from html import escape
from pathlib import Path
from typing import Final

from patentic.report.bundle import LABEL, CandidateReport, ReportBundle
from patentic.report.deck_content import (
    COMMERCIAL_NOTES,
    FLOW,
    NEXT_STEPS,
    SLIDES,
    WORKFLOW_NOTES,
    all_evidence,
    narrowing,
    objective,
    risks,
    shortlisted,
    sources,
)
from patentic.report.docx_renderer import COMPARISON_HEADER
from patentic.report.formatters import fmt_confidence, fmt_date, fmt_score, fmt_source, fmt_status

ASSETS: Final[Path] = Path(__file__).parent / "assets"
MAX_SCORE: Final[float] = 5.0

Writer = Callable[[ReportBundle], tuple[str, str, str]]


def e(text: object) -> str:
    return escape(str(text), quote=True)


def render_html(bundle: ReportBundle, out: Path) -> Path:
    writers: tuple[Writer, ...] = (
        _objective,
        _workflow,
        _scope,
        _comparison,
        _status_example,
        _technical,
        _commercial,
        _risks,
    )
    sections: list[str] = [_title(bundle)]
    for number, (title, writer) in enumerate(zip(SLIDES[1:], writers, strict=True), start=2):
        takeaway, body, notes = writer(bundle)
        sections.append(_slide(bundle, number, title, takeaway, body, notes))
    parts: dict[str, str] = {
        "title": e(f"Expired-patent screening: {bundle.request.technology_category}"),
        "css": (ASSETS / "deck.css").read_text(),
        "js": (ASSETS / "deck.js").read_text(),
        "slides": "\n".join(sections),
    }
    # One pass, so braces in CSS, JS or patent text are never treated as placeholders.
    page: str = re.sub(r"\{(title|css|js|slides)\}", lambda m: parts[m.group(1)], _PAGE)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    return out


def _slide(
    bundle: ReportBundle, number: int, title: str, takeaway: str, body: str, notes: str
) -> str:
    lead: str = f'<p class="takeaway">{e(takeaway)}</p>' if takeaway else ""
    aside: str = f'<aside class="notes">{e(notes)}</aside>' if notes else ""
    return (
        f'<section class="slide" data-title="{e(title)}">'
        f"<h2>{e(title)}</h2>{lead}"
        f'<div class="body">{body}</div>{aside}'
        f'<div class="footer"><span>{e(LABEL)}</span>'
        f"<span>Run {e(bundle.run.thread_id)} &middot; {number} / {len(SLIDES)}</span></div>"
        "</section>"
    )


def _title(bundle: ReportBundle) -> str:
    return (
        f'<section class="slide title" data-title="{e(SLIDES[0])}">'
        f"<h1>Expired-patent screening: {e(bundle.request.technology_category)}</h1>"
        '<p class="sub">US patents that appear to have lapsed for nonpayment of maintenance fees</p>'
        f'<p class="meta">Run {e(bundle.run.thread_id)}<br>'
        f"{bundle.run.created:%Y-%m-%d} &middot; US patents only</p>"
        f'<div class="label">{e(LABEL)}</div>'
        "</section>"
    )


def _list(items: Sequence[str], css: str = "plain") -> str:
    tag: str = "ol" if css == "points" else "ul"
    rows: str = "".join(f"<li>{e(item)}</li>" for item in items)
    return f'<{tag} class="{css}">{rows}</{tag}>'


def _objective(bundle: ReportBundle) -> tuple[str, str, str]:
    request = bundle.request
    left: str = (
        f'<div class="col narrow"><p class="lead">{e(request.technology_category.capitalize())}</p>'
        f'<p class="lead-sub">{e(request.intended_product or "")}</p></div>'
    )
    right: str = f'<div class="col">{_list(objective(bundle), "points")}</div>'
    return "What the run was asked to find, and what it does not claim.", left + right, ""


def _workflow(_bundle: ReportBundle) -> tuple[str, str, str]:
    steps: str = "".join(
        f'<div class="step{" gate" if gate else ""}"><span class="n">{i}</span>{e(label)}</div>'
        for i, (label, gate) in enumerate(FLOW, start=1)
    )
    notes: str = "".join(f"<p>{e(line)}</p>" for line in WORKFLOW_NOTES)
    body: str = (
        f'<div class="col"><div class="flow">{steps}</div>'
        '<p class="legend"><span class="swatch"></span>The run pauses for a person at these two steps.</p>'
        f'<div class="notes-row">{notes}</div></div>'
    )
    return (
        "A fixed workflow: code fetches and judges the evidence, the model only drafts text.",
        body,
        "Amber boxes are human gates; the run pauses there.",
    )


def _scope(bundle: ReportBundle) -> tuple[str, str, str]:
    stages: list[tuple[str, int]] = narrowing(bundle)
    top: int = max((n for _, n in stages), default=0) or 1
    rows: str = "".join(
        f'<div class="row"><div><div class="what">{e(what)}</div>'
        f'<div class="bar"><span style="width:{max(n / top * 100, 0.6 if n else 0):.1f}%"></span></div></div>'
        f'<div class="num">{n:,}</div></div>'
        for what, n in stages
    )
    source_rows: str = "".join(
        f"<tr><td>{e(name)}</td><td>{e(detail)}</td><td>{e(grade)}</td></tr>"
        for name, detail, grade in sources(bundle)
    )
    cpc: str = ", ".join(bundle.plan.cpc_codes[:8]) or "n/a"
    body: str = (
        f'<div class="col narrow"><div class="funnel">{rows}</div></div>'
        '<div class="col"><table><thead><tr><th>Source</th><th>What it gave</th><th>Grade</th></tr></thead>'
        f'<tbody>{source_rows}</tbody></table><p class="cpc">CPC groups searched: {e(cpc)}</p></div>'
    )
    flow = bundle.flow
    return (
        f"{flow.found:,} patents searched; {flow.recommended} recommended for review.",
        body,
        "",
    )


def _chip(label: str) -> str:
    return f'<span class="chip {e(label)}">{e(fmt_status(label))}</span>'


def _comparison(bundle: ReportBundle) -> tuple[str, str, str]:
    if not bundle.candidates:
        return "", '<p class="empty">No candidate passed the evidence and screening checks.</p>', ""
    synthetic: bool = any(c.is_synthetic for c in bundle.candidates)
    banner: str = (
        '<p class="banner">SYNTHETIC FIXTURE: made-up patents used to test the pipeline.</p>'
        if synthetic
        else ""
    )
    head: str = "".join(f"<th>{e(h)}</th>" for h in COMPARISON_HEADER)
    rows: str = "".join(
        f'<tr class="{"shortlist" if c.recommendation == "Shortlist" else ""}">'
        f"<td>{e(c.display)}</td><td>{e(c.title)}</td>"
        f'<td data-status="{e(fmt_status(c.status.label))}">{_chip(c.status.label)}</td>'
        f"<td>{e(fmt_confidence(c.status.confidence))}</td>"
        f'<td class="num">{e(fmt_score(c.scores.total if c.scores else None))}</td>'
        f"<td>{e(c.recommendation)}</td></tr>"
        for c in bundle.candidates
    )
    body: str = (
        f'<div class="col">{banner}<table class="comparison"><thead><tr>{head}</tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )
    count: int = len(bundle.shortlist)
    return (
        f"{len(bundle.candidates)} candidates scored; {count} shortlisted (highlighted).",
        body,
        all_evidence(bundle),
    )


def _status_example(bundle: ReportBundle) -> tuple[str, str, str]:
    example: CandidateReport | None = bundle.illustration or (
        bundle.candidates[0] if bundle.candidates else None
    )
    if example is None:
        return "", '<p class="empty">No status example is available for this run.</p>', ""
    rows: str = "".join(
        f'<li><span class="date">{e(fmt_date(r.date))}</span><span>{e(r.event)}</span>'
        f'<span class="src">{e(fmt_source(r.source))} ({e(r.grade)})</span></li>'
        for r in example.timeline[:10]
    )
    status: str = (
        f'<p class="status-line"><strong>{e(example.display)}</strong> {e(example.title)} '
        f"&middot; {_chip(example.status.label)} &middot; confidence "
        f"{e(fmt_confidence(example.status.confidence))}</p>"
    )
    note: str = bundle.illustration_note or " ".join(example.status.notes)
    body: str = (
        f'<div class="col">{status}<ul class="timeline">{rows}</ul></div>'
        f'<div class="col note"><p class="aside-note">{e(note)}</p></div>'
    )
    return (
        "Every status is dated and sourced; a later official notice overrides an earlier one.",
        body,
        "Evidence: " + ", ".join(example.evidence_ids),
    )


def _technical(bundle: ReportBundle) -> tuple[str, str, str]:
    chosen: list[CandidateReport] = shortlisted(bundle)
    if not chosen:
        return (
            "",
            '<p class="empty">No candidate was shortlisted, so no technical opportunity is presented.</p>',
            "",
        )
    cards: str = ""
    for report in chosen:
        tech = report.technical
        if tech is None:
            continue
        cards += (
            f'<div class="card"><div class="id">{e(report.display)}</div><h3>{e(report.title)}</h3>'
            f"<p>{e(tech.summary)}</p>"
            f"<h4>Key claim elements</h4>{_list(tech.key_claim_elements[:3])}"
            f"<h4>Open questions</h4>{_list(tech.implementation_unknowns[:3] or ['None recorded'])}"
            "</div>"
        )
    return (
        "What the shortlisted patents claim, and what a prototype would need to settle.",
        cards,
        all_evidence(bundle),
    )


def _commercial(bundle: ReportBundle) -> tuple[str, str, str]:
    scored: list[CandidateReport] = [c for c in bundle.candidates if c.scores]
    if not scored:
        return "", '<p class="empty">No candidate was scored.</p>', ""
    rows: str = "".join(
        f'<div class="row{" shortlist" if c.recommendation == "Shortlist" else ""}">'
        f"<span>{e(c.display)}</span>"
        f'<div class="track"><div class="fill" style="width:{c.scores.total / MAX_SCORE * 100:.1f}%"></div></div>'
        f'<span class="val">{e(fmt_score(c.scores.total))}</span></div>'
        for c in scored
        if c.scores
    )
    weights = bundle.weights
    weight_text: str = (
        f"Weights: commercial relevance {weights.commercial_relevance:.0%}, engineering effort "
        f"{weights.engineering_effort:.0%}, evidence quality {weights.evidence_quality:.0%}, "
        f"unresolved risk {weights.unresolved_risk:.0%}."
    )
    body: str = (
        f'<div class="col"><div class="chart">{rows}</div>'
        '<p class="chart-caption">Total score out of 5. Navy bars are shortlisted.</p></div>'
        f'<div class="col narrow">{_list(COMMERCIAL_NOTES)}'
        f'<p class="weights cpc">{e(weight_text)}</p></div>'
    )
    return "How the candidates compare on the weighted score.", body, weight_text


def _risks(bundle: ReportBundle) -> tuple[str, str, str]:
    body: str = (
        f'<div class="col"><h3>Unresolved risks</h3>{_list(risks(bundle))}</div>'
        f'<div class="col"><h3>Next steps</h3>{_list(NEXT_STEPS, "points")}'
        f'<p class="label-strong">{e(LABEL)}</p></div>'
    )
    return "Treat every candidate as a lead to check, not a product to build yet.", body, ""


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
<main class="viewport"><div class="stage">
{slides}
</div></main>
<nav class="controls" aria-label="Slide navigation">
<button id="prev" type="button">Previous</button>
<span id="count" class="count" aria-live="polite"></span>
<button id="next" type="button">Next</button>
<span class="hint">Arrow keys to move, N for notes</span>
</nav>
<script>
{js}
</script>
</body>
</html>
"""
