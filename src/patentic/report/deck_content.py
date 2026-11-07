from typing import Final

from patentic.report.bundle import CandidateReport, ReportBundle
from patentic.report.formatters import fmt_date

SLIDES: Final[tuple[str, ...]] = (
    "Title",
    "Business objective",
    "Agent workflow and architecture",
    "Search scope and evidence sources",
    "Candidate comparison",
    "Status-verification example",
    "Technical opportunity",
    "Commercial assessment",
    "Unresolved risks and next steps",
)
FLOW: Final[tuple[tuple[str, bool], ...]] = (
    ("Intake", False),
    ("Plan (model)", False),
    ("Approval (you)", True),
    ("Discovery: BigQuery", False),
    ("Gazette index", False),
    ("Claims and continuity", False),
    ("Screen and verify status", False),
    ("Analyse (model)", False),
    ("Score", False),
    ("Review (you)", True),
    ("Report and deck", False),
)
WORKFLOW_NOTES: Final[tuple[str, ...]] = (
    "Code makes every data call and applies the status rules; the model drafts the plan, summarises claims and writes prose.",
    "Every claim in the outputs points to an evidence record with its source URL and retrieval time.",
)
COMMERCIAL_NOTES: Final[tuple[str, ...]] = (
    "Scores run 1 to 5; effort and risk count against a candidate.",
    "Owners who stop paying usually judged the patent worth little to them; each case needs a reason that does not bind a new entrant.",
    "US housekeeping-supplies spending: $844 per household in 2025 (BLS). Category context only.",
)


def objective(bundle: ReportBundle) -> list[str]:
    return [
        f"Find US patents in {bundle.request.technology_category} that appear to have expired for nonpayment.",
        "Verify each status over time, including later reinstatement.",
        (
            f"Rank up to {bundle.request.max_candidates} candidates and recommend up to "
            f"{bundle.request.max_recommended} for technical and legal review."
        ),
        "Evidence-backed screening, not a claim that the technology is free to use.",
    ]


def sources(bundle: ReportBundle) -> list[tuple[str, str, str]]:
    coverage = bundle.coverage
    return [
        (
            "Official Gazette notices",
            f"{coverage.weeks_fetched} weekly issues, last issue {fmt_date(coverage.last_issue)}",
            "A",
        ),
        (
            "BigQuery PatentsView",
            "Bibliographic data, claims, citations, continuity (grants to 2021-09-28)",
            "A",
        ),
        (
            "EPO OPS legal events",
            "Used as a cross-check" if bundle.run.ops_configured else "Not configured for this run",
            "B",
        ),
    ]


def scope(bundle: ReportBundle) -> list[str]:
    flow = bundle.flow
    return [
        f"CPC groups: {', '.join(bundle.plan.cpc_codes[:8]) or 'n/a'}.",
        *(f"{name}: {detail} (grade {grade})." for name, detail, grade in sources(bundle)),
        (
            f"Narrowing: {flow.found} found, {flow.expired_in_window} expired in window, "
            f"{flow.passed_screening} non-powered, {flow.analysed} analysed, {flow.recommended} recommended."
        ),
    ]


def narrowing(bundle: ReportBundle) -> list[tuple[str, int]]:
    flow = bundle.flow
    return [
        ("Found in the cleaning-tool CPC groups", flow.found),
        ("Listed as expired for nonpayment", flow.expired_in_window),
        ("Passed the non-powered screen", flow.passed_screening),
        ("Analysed and scored", flow.analysed),
        ("Recommended for review", flow.recommended),
    ]


def shortlisted(bundle: ReportBundle) -> list[CandidateReport]:
    return [
        c for c in bundle.candidates if c.recommendation == "Shortlist" and c.technical is not None
    ]


def technical(bundle: ReportBundle) -> list[str]:
    lines: list[str] = []
    for report in shortlisted(bundle):
        if report.technical is None:
            continue
        lines.append(f"{report.display}: {report.technical.summary}")
        if report.technical.implementation_unknowns:
            lines.append(
                "Open questions: " + "; ".join(report.technical.implementation_unknowns[:3])
            )
    return lines or ["No candidate was shortlisted, so no technical opportunity is presented."]


def risks(bundle: ReportBundle) -> list[str]:
    related: int = sum(len(c.related) for c in bundle.candidates)
    return [
        f"{related} related records (continuations, citations, same owner) need their own status check.",
        "A lapsed patent can be reinstated; recent lapses carry the most risk.",
        "Design patents and trade dress may cover the product's look.",
    ]


NEXT_STEPS: Final[tuple[str, ...]] = (
    "Confirm each status in USPTO Patent Center and check for a pending petition.",
    "Read the full claims and drawings; build a test sample before tooling.",
    "Have a patent attorney run a freedom-to-operate search, including related patents.",
)


def all_evidence(bundle: ReportBundle) -> str:
    ids: list[str] = [e for c in bundle.candidates for e in c.evidence_ids]
    return "Evidence: " + ", ".join(ids) if ids else ""
