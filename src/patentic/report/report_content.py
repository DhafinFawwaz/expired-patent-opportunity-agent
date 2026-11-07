from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from patentic.report.bundle import LABEL, CandidateReport, ReportBundle
from patentic.report.formatters import (
    fmt_confidence,
    fmt_date,
    fmt_score,
    fmt_source,
    fmt_status,
)

SECTIONS: Final[tuple[str, ...]] = (
    "Executive summary",
    "Search scope and methodology",
    "Candidate comparison",
    "Patent-status evidence timelines",
    "Technical and claims summaries",
    "Related-patent findings",
    "Commercial opportunity assessment",
    "Recommended shortlist and rationale",
    "Engineering validation and specialist-review next steps",
    "Limitations, assumptions and references",
)
PAGE_BREAK_BEFORE: Final[frozenset[int]] = frozenset({3, 5, 7, 10})
COMPARISON_HEADER: Final[tuple[str, ...]] = (
    "Patent",
    "Title",
    "Status",
    "Confidence",
    "Score",
    "Recommendation",
)
SYNTHETIC_NOTE: Final[str] = (
    "SYNTHETIC FIXTURE: made-up patents used to test the pipeline, not research results."
)
NEXT_STEPS: Final[tuple[str, ...]] = (
    "Confirm each status in USPTO Patent Center and check for a pending petition.",
    "Read the full claims and drawings; build a test sample before tooling.",
    "Have a patent attorney run a freedom-to-operate search, including related patents.",
    "Check design patents and trade dress that may cover the product's look.",
)

ParaKind = Literal["body", "caption", "disclaimer", "banner"]


@dataclass(frozen=True)
class Heading:
    text: str
    level: int


@dataclass(frozen=True)
class Para:
    text: str
    kind: ParaKind = "body"


@dataclass(frozen=True)
class Bullets:
    items: tuple[str, ...]


@dataclass(frozen=True)
class Table:
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    highlight: frozenset[int] = field(default_factory=frozenset)
    role: Literal["comparison", "other"] = "other"


@dataclass(frozen=True)
class Reference:
    number: int
    title: str
    retrieved: str
    url: str


@dataclass(frozen=True)
class PageBreak:
    pass


Block = Heading | Para | Bullets | Table | Reference | PageBreak


def report_title(bundle: ReportBundle) -> str:
    return f"Expired-patent screening: {bundle.request.technology_category}"


def report_meta(bundle: ReportBundle) -> str:
    return f"Run {bundle.run.thread_id}, {bundle.run.created:%Y-%m-%d}. US patents only."


def report_blocks(bundle: ReportBundle) -> list[Block]:
    writers = (
        _executive,
        _methodology,
        _comparison,
        _timelines,
        _technical,
        _related,
        _commercial,
        _shortlist,
        _next_steps,
        _limitations,
    )
    blocks: list[Block] = []
    for number, (title, writer) in enumerate(zip(SECTIONS, writers, strict=True), start=1):
        if number in PAGE_BREAK_BEFORE:
            blocks.append(PageBreak())
        blocks.append(Heading(f"{number}. {title}", 1))
        blocks.extend(writer(bundle))
    return blocks


def _executive(bundle: ReportBundle) -> list[Block]:
    return [Para(bundle.prose.get("executive_summary", ""))]


def _methodology(bundle: ReportBundle) -> list[Block]:
    flow = bundle.flow
    plan = bundle.plan
    return [
        Para(bundle.prose.get("methodology", "")),
        Bullets(tuple(bundle.methodology)),
        Para("How the candidate set narrowed:", "caption"),
        Table(
            ("Step", "Patents"),
            (
                ("Found in the cleaning-tool CPC groups", str(flow.found)),
                ("Listed as expired for nonpayment in the window", str(flow.expired_in_window)),
                ("Passed the non-powered screen", str(flow.passed_screening)),
                ("Status verified", str(flow.status_verified)),
                ("Analysed and scored", str(flow.analysed)),
                ("Eligible but not analysed (capacity)", str(flow.not_analysed)),
                ("Recommended for review", str(flow.recommended)),
            ),
        ),
        Para(f"CPC prefixes searched: {', '.join(plan.cpc_codes) or 'n/a'}."),
        Para(f"Sources: {'; '.join(plan.sources) or 'n/a'}."),
    ]


def comparison_rows(candidates: Sequence[CandidateReport]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        (
            c.display,
            c.title,
            fmt_status(c.status.label),
            fmt_confidence(c.status.confidence),
            fmt_score(c.scores.total if c.scores else None),
            c.recommendation,
        )
        for c in candidates
    )


def _comparison_table(candidates: Sequence[CandidateReport]) -> Table:
    chosen: frozenset[int] = frozenset(
        i for i, c in enumerate(candidates) if c.recommendation == "Shortlist"
    )
    return Table(COMPARISON_HEADER, comparison_rows(candidates), chosen, "comparison")


def _comparison(bundle: ReportBundle) -> list[Block]:
    if not bundle.candidates:
        return [Para("No candidate passed the evidence and screening checks.")]
    real: list[CandidateReport] = [c for c in bundle.candidates if not c.is_synthetic]
    synthetic: list[CandidateReport] = [c for c in bundle.candidates if c.is_synthetic]
    blocks: list[Block] = []
    if real:
        blocks.append(_comparison_table(real))
    if synthetic:
        blocks += [Para(SYNTHETIC_NOTE, "banner"), _comparison_table(synthetic)]
    return blocks


def _timeline(report: CandidateReport) -> list[Block]:
    status = report.status
    blocks: list[Block] = [
        Heading(f"{report.display}: {report.title}", 2),
        Para(
            f"Status: {fmt_status(status.label)} as of {fmt_date(status.as_of)}, "
            f"confidence {fmt_confidence(status.confidence)}."
        ),
        Table(
            ("Date", "Event", "Source", "Grade"),
            tuple(
                (fmt_date(r.date), r.event, fmt_source(r.source), r.grade) for r in report.timeline
            ),
        ),
    ]
    blocks += [Para(note, "disclaimer") for note in status.notes]
    return blocks


def _timelines(bundle: ReportBundle) -> list[Block]:
    blocks: list[Block] = []
    for report in bundle.candidates:
        blocks += _timeline(report)
    if bundle.illustration:
        blocks.append(Para(f"Worked example. {bundle.illustration_note}"))
        blocks += _timeline(bundle.illustration)
    return blocks


def _technical(bundle: ReportBundle) -> list[Block]:
    blocks: list[Block] = []
    for report in bundle.candidates:
        blocks.append(Heading(f"{report.display}: {report.title}", 2))
        technical = report.technical
        if technical is None:
            blocks.append(Para("Not summarised."))
            continue
        blocks += [
            Para(technical.summary),
            Para(f"Mechanism: {technical.mechanism}"),
            Bullets(tuple(f"Claim element: {e}" for e in technical.key_claim_elements)),
            Bullets(tuple(f"Unknown: {u}" for u in technical.implementation_unknowns)),
        ]
    return blocks


def _related(bundle: ReportBundle) -> list[Block]:
    blocks: list[Block] = []
    for report in bundle.candidates:
        blocks.append(Heading(report.display, 2))
        if not report.related:
            blocks.append(Para("No related records were found in the public data checked."))
            continue
        blocks.append(
            Table(
                ("Relation", "Record", "Evidence", "Status"),
                tuple((r.relation, r.patent_key, r.evidence, "to verify") for r in report.related),
            )
        )
    return blocks


def _commercial(bundle: ReportBundle) -> list[Block]:
    weights = bundle.weights
    rows: tuple[tuple[str, ...], ...] = tuple(
        (
            c.display,
            str(c.scores.commercial_relevance),
            str(c.scores.engineering_effort),
            str(c.scores.evidence_quality),
            str(c.scores.unresolved_risk),
            fmt_score(c.scores.total),
        )
        for c in bundle.candidates
        if c.scores
    )
    return [
        Para(bundle.prose.get("commercial", "")),
        Para(
            f"Weights: commercial relevance {weights.commercial_relevance:.0%}, engineering effort "
            f"{weights.engineering_effort:.0%} (inverted), evidence quality "
            f"{weights.evidence_quality:.0%}, "
            f"unresolved risk {weights.unresolved_risk:.0%} (inverted). Scores run from 1 to 5.",
            "caption",
        ),
        Table(("Patent", "Commercial", "Effort", "Evidence", "Risk", "Total"), rows),
    ]


def _shortlist(bundle: ReportBundle) -> list[Block]:
    chosen: list[CandidateReport] = [
        c for c in bundle.candidates if c.recommendation == "Shortlist"
    ]
    if not chosen:
        return [Para("No candidate is recommended.")]
    blocks: list[Block] = []
    for report in chosen:
        rationale: str = report.opportunity.rationale if report.opportunity else ""
        blocks += [
            Heading(f"{report.display}: {report.title}", 2),
            Para(rationale or "No rationale was generated."),
        ]
        if report.reviewer_note:
            blocks.append(Para(f"Reviewer note: {report.reviewer_note}"))
    return blocks


def _next_steps(bundle: ReportBundle) -> list[Block]:
    return [Para(bundle.prose.get("next_steps", "")), Bullets(NEXT_STEPS)]


def _limitations(bundle: ReportBundle) -> list[Block]:
    blocks: list[Block] = [
        Para(LABEL, "disclaimer"),
        Heading("Limitations", 2),
        Bullets(tuple(bundle.limitations)),
        Heading("Key assumptions", 2),
        Bullets(tuple(bundle.key_assumptions)),
        Heading("Quality of information", 2),
        Bullets(tuple(bundle.quality_of_information)),
        Heading("References", 2),
    ]
    blocks += [
        Reference(number, ref.title, str(ref.retrieved), ref.url)
        for number, ref in enumerate(bundle.references, start=1)
    ]
    return blocks
