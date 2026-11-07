from datetime import date
from typing import TYPE_CHECKING, Final

from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict

from patentic.adapters.base import EvidenceRecord
from patentic.adapters.http import utc_now
from patentic.domain.confidence import grade_for_source
from patentic.domain.coverage import ScanCoverage
from patentic.domain.status_rules import StatusAssessment, assess_status
from patentic.graph.deps import Deps
from patentic.graph.progress import emit
from patentic.graph.state import Candidate, PipelineState
from patentic.llm.schemas import CallMeta, PlanDraft
from patentic.report.bundle import (
    CandidateReport,
    FlowCounts,
    Reference,
    ReportBundle,
    RunInfo,
    TimelineRow,
)
from patentic.report.formatters import fmt_event, fmt_patent, fmt_source, fmt_status
from patentic.report.illustration import ILLUSTRATION_KEY, Observation, load_observation
from patentic.report.static_refs import STATIC_REFERENCES

if TYPE_CHECKING:
    from pathlib import Path

    from patentic.domain.events import StatusEvent

BUDGETS: Final[dict[str, int]] = {
    "executive_summary": 250,
    "methodology": 350,
    "commercial": 300,
    "next_steps": 200,
}


class BundleUpdate(TypedDict, total=False):
    stage: str
    bundle_path: str
    calls: list[CallMeta]


def timeline_rows(
    assessment: StatusAssessment, grant: date | None = None, coverage: ScanCoverage | None = None
) -> list[TimelineRow]:
    rows: list[TimelineRow] = [
        TimelineRow(
            date=e.event_date,
            event=fmt_event(e.event_type, e.effective_date),
            source=e.source,
            grade=grade_for_source(e.source, "status"),
            evidence_id=e.evidence_id,
        )
        for e in assessment.timeline
    ]
    # Derived rows carry no evidence id; the bundle's reference check skips them.
    if grant is not None:
        granted: TimelineRow = TimelineRow(
            date=grant,
            event="Granted",
            source="bigquery",
            grade=grade_for_source("bigquery", "bibliographic"),
            evidence_id="",
        )
        rows.insert(0, granted)
    scanned: bool = coverage is not None and coverage.first_issue is not None
    if scanned and coverage and coverage.last_issue and assessment.label == "expired_nonpayment":
        rows.append(
            TimelineRow(
                date=coverage.last_issue,
                event=(
                    f"No reinstatement listed in Gazette issues {coverage.first_issue} "
                    f"to {coverage.last_issue}"
                ),
                source="og_notice",
                grade=grade_for_source("og_notice", "status"),
                evidence_id="",
            )
        )
    return rows


def _cited(rows: list[TimelineRow]) -> list[str]:
    return [row.evidence_id for row in rows if row.evidence_id]


def candidate_report(candidate: Candidate, coverage: ScanCoverage | None = None) -> CandidateReport:
    assessment: StatusAssessment = candidate.assessment or StatusAssessment(
        label="unknown", as_of=date.min
    )
    recommendation = (
        candidate.recommendation
        if candidate.recommendation in {"Shortlist", "Hold", "Exclude"}
        else "Hold"
    )
    return CandidateReport(
        key=candidate.key,
        display=fmt_patent(candidate.key),
        title=candidate.record.title,
        grant_date=candidate.record.grant_date,
        filing_date=candidate.record.filing_date,
        cpc_codes=candidate.record.cpc_codes,
        status=assessment,
        timeline=timeline_rows(assessment, candidate.record.grant_date, coverage),
        technical=candidate.technical,
        opportunity=candidate.opportunity,
        related=candidate.related,
        flags=candidate.flags,
        scores=candidate.scores,
        recommendation=recommendation,
        reviewer_note=candidate.reviewer_note,
        is_synthetic=candidate.is_synthetic,
        evidence_ids=_cited(timeline_rows(assessment)),
    )


class Bundle:
    def __init__(self, deps: Deps) -> None:
        self._deps: Deps = deps

    def __call__(self, state: PipelineState, config: RunnableConfig) -> BundleUpdate:
        deps: Deps = self._deps
        thread_id: str = str(config.get("configurable", {}).get("thread_id", "run"))
        request = state["request"]
        candidates: dict[str, Candidate] = state.get("candidates", {})
        evidence: dict[str, EvidenceRecord] = dict(state.get("evidence", {}))
        analysed: list[Candidate] = sorted(
            (c for c in candidates.values() if c.scores is not None),
            key=lambda c: (-(c.scores.total if c.scores else 0.0), c.key),
        )
        coverage: ScanCoverage = state.get("coverage") or ScanCoverage(weeks_fetched=0)
        reports: list[CandidateReport] = [
            candidate_report(c, coverage) for c in analysed[: request.max_candidates]
        ]
        shortlist: list[str] = [r.key for r in reports if r.recommendation == "Shortlist"]
        illustration, note = self._illustration(state, candidates, coverage, evidence)
        flow: FlowCounts = FlowCounts(
            found=len(state.get("records", {})),
            expired_in_window=len(candidates),
            passed_screening=sum(1 for c in candidates.values() if c.screening.passed),
            status_verified=sum(1 for c in candidates.values() if c.assessment is not None),
            analysed=len(state.get("pool", [])),
            not_analysed=sum(1 for c in candidates.values() if c.recommendation == "NotAnalysed"),
            recommended=len(shortlist),
        )
        calls: list[CallMeta] = list(state.get("calls", []))
        outages: list[str] = list(state.get("outages", []))
        prose, prose_calls = self._prose(reports, flow, request.lapse_window_weeks, outages)
        cited: set[str] = {e for r in reports for e in r.evidence_ids}
        if illustration:
            cited |= set(illustration.evidence_ids)
        references: list[Reference] = [
            *STATIC_REFERENCES,
            *(_reference(evidence[e]) for e in sorted(cited) if e in evidence),
            *(
                Reference(
                    id=e, title="Synthetic or unrecorded evidence", url="n/a", retrieved=deps.today
                )
                for e in sorted(cited)
                if e not in evidence
            ),
        ]
        all_calls: list[CallMeta] = [*calls, *prose_calls]
        bundle: ReportBundle = ReportBundle(
            run=RunInfo(
                thread_id=thread_id,
                created=utc_now(),
                is_demo=bool(deps.fixtures),
                model=", ".join(sorted({c.model for c in all_calls})) or "none",
                llm_calls=len(all_calls),
                fallback_calls=sum(1 for c in all_calls if c.method == "fallback"),
                bigquery_bytes=deps.bq.ledger.total(),
                outages=outages,
                ops_configured=deps.ops.enabled,
            ),
            request=request,
            plan=state.get("plan")
            or PlanDraft(
                search_terms=[],
                cpc_codes=[],
                exclusion_terms=[],
                sources=[],
                screening_criteria=[],
                output_structure=[],
            ),
            coverage=coverage,
            flow=flow,
            candidates=reports,
            illustration=illustration,
            illustration_note=note,
            shortlist=shortlist,
            weights=deps.weights,
            prose=prose,
            methodology=_methodology(coverage, request.lapse_window_weeks),
            key_assumptions=_assumptions(coverage),
            quality_of_information=_quality(deps.ops.enabled, outages, flow),
            limitations=_limitations(flow, request.max_candidates, deps.ops.enabled),
            references=references,
        )
        run_dir: Path = deps.settings.patentic_outputs_dir / "runs" / thread_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path: Path = run_dir / "bundle.json"
        path.write_text(bundle.model_dump_json(indent=2))
        emit("generation", "bundle_written", candidates=len(reports), shortlist=len(shortlist))
        return {"stage": "bundle", "bundle_path": str(path), "calls": prose_calls}

    def _illustration(
        self,
        state: PipelineState,
        candidates: dict[str, Candidate],
        coverage: ScanCoverage,
        evidence: dict[str, EvidenceRecord],
    ) -> tuple[CandidateReport | None, str]:
        if self._deps.fixtures:
            reinstated: list[Candidate] = [
                c
                for c in candidates.values()
                if c.assessment and c.assessment.label == "reinstated"
            ]
            if not reinstated:
                return None, ""
            report: CandidateReport = candidate_report(reinstated[0], coverage).model_copy(
                update={"recommendation": "Exclude"}
            )
            return report, "Synthetic fixture: an expiry notice followed by a reinstatement notice."
        observation: Observation | None = load_observation()
        if observation is None:
            return None, ""
        official: list[StatusEvent] = state.get("events", {}).get(ILLUSTRATION_KEY, [])
        for item in observation.evidence:
            evidence[item.evidence_id] = item
        from patentic.domain.identifiers import parse_patent_number  # noqa: PLC0415

        assessment: StatusAssessment = assess_status(
            parse_patent_number(observation.patent_key),
            observation.grant_date,
            observation.filing_date,
            [*official, *observation.events],
            coverage,
            self._deps.today,
        )
        report = CandidateReport(
            key=observation.patent_key,
            display=fmt_patent(observation.patent_key),
            title=observation.title,
            grant_date=observation.grant_date,
            filing_date=observation.filing_date,
            cpc_codes=[],
            status=assessment,
            timeline=timeline_rows(assessment, observation.grant_date, coverage),
            recommendation="Exclude",
            evidence_ids=_cited(timeline_rows(assessment)),
        )
        found: str = "is in" if official else "is not in"
        note: str = (
            f"Not a cleaning tool; shown because the official record and a secondary display disagree. "
            f"The Gazette reinstatement row {found} this run's scan window. {observation.note}"
        )
        return report, note

    def _prose(
        self, reports: list[CandidateReport], flow: FlowCounts, weeks: int, outages: list[str]
    ) -> tuple[dict[str, str], list[CallMeta]]:
        facts: dict[str, object] = {
            "flow": flow.model_dump(),
            "weeks": weeks,
            "outages": outages,
            "candidates": [
                {
                    "patent": r.display,
                    "title": r.title,
                    "status": fmt_status(r.status.label),
                    "confidence": r.status.confidence,
                    "score": r.scores.total if r.scores else None,
                    "recommendation": r.recommendation,
                    "rationale": r.opportunity.rationale if r.opportunity else "",
                }
                for r in reports
            ],
        }
        fallbacks: dict[str, str] = {
            "executive_summary": _executive_fallback(reports, flow, weeks),
            "methodology": _methodology_fallback(flow, weeks),
            "commercial": _commercial_fallback(reports),
            "next_steps": _next_steps_fallback(reports),
        }
        prose: dict[str, str] = {}
        calls: list[CallMeta] = []
        for section, budget in BUDGETS.items():
            result, meta = self._deps.llm.prose(
                section, {**facts, "fallback": fallbacks[section]}, budget
            )
            prose[section] = result.text
            calls.append(meta)
        return prose, calls


def _reference(item: EvidenceRecord) -> Reference:
    return Reference(
        id=item.evidence_id,
        title=f"{fmt_source(item.source)}: {item.raw_snippet[:90]}",
        url=item.url,
        retrieved=item.retrieved_at.date(),
    )


def _executive_fallback(reports: list[CandidateReport], flow: FlowCounts, weeks: int) -> str:
    names: str = ", ".join(
        f"{r.display} ({r.title})" for r in reports if r.recommendation == "Shortlist"
    )
    text: str = (
        f"The run looked at {flow.found} US utility patents in the cleaning-tool CPC groups. "
        f"{flow.expired_in_window} of them appear in Official Gazette expiration notices from the last {weeks} weeks, "
        f"{flow.passed_screening} passed the non-powered screen and {flow.analysed} were analysed. "
    )
    text += (
        f"Recommended for technical and legal review: {names}. "
        if names
        else "No candidate met the bar for a recommendation. "
    )
    if len(reports) < 5:  # noqa: PLR2004
        text += f"Only {len(reports)} candidates are reported because fewer passed the evidence and screening checks. "
    return (
        text
        + "Every status is dated and comes from public notices; none of this is legal clearance."
    )


def _methodology_fallback(flow: FlowCounts, weeks: int) -> str:
    return (
        "Candidates came from the BigQuery PatentsView tables, filtered to core cleaning-tool CPC groups. "
        f"Their patent numbers were matched against {weeks} weeks of Official Gazette expiration notices. "
        "Patents with a powered co-classification or a power source in an independent claim were removed. "
        "Every later reinstatement list was scanned before a patent was called expired, and confidence was set by rule "
        f"from the number of sources and the completeness of that scan. {flow.analysed} candidates were summarised and scored."
    )


def _commercial_fallback(reports: list[CandidateReport]) -> str:
    lines: list[str] = [
        f"{r.display}: commercial relevance {r.scores.commercial_relevance}/5, engineering effort {r.scores.engineering_effort}/5."
        for r in reports
        if r.scores
    ]
    return " ".join(
        [
            *lines,
            "US consumer units spent an average of $844 on housekeeping supplies in 2025 (BLS); that is category context, not a market size for any candidate.",
            "An owner who stops paying maintenance fees usually judged the patent worth little to them, so each case needs a reason that judgement does not apply to a new entrant.",
        ]
    )


def _next_steps_fallback(reports: list[CandidateReport]) -> str:
    shortlisted: list[str] = [r.display for r in reports if r.recommendation == "Shortlist"]
    target: str = ", ".join(shortlisted) or "any candidate taken forward"
    return (
        f"For {target}: confirm the current status in USPTO Patent Center, read the full claims and drawings, "
        "search for live continuations, divisionals and later patents from the same owner, and have a patent attorney run a "
        "freedom-to-operate search before any design work."
    )


def _methodology(coverage: ScanCoverage, weeks: int) -> list[str]:
    return [
        "Search: CPC prefixes for non-powered household cleaning tools (A47L 13, A47L 1, A47L 17, A47K 11/10 and related groups).",
        f"Status source: Official Gazette notices, {coverage.weeks_fetched} weekly issues fetched out of {weeks} requested.",
        "Screening: powered co-classes removed, power terms in independent claims removed, unclear cases flagged.",
        "Status rules: a later official notice wins; expired means listed as expired with no later reinstatement found.",
        "Scoring: commercial relevance 35%, engineering effort 20% (inverted), evidence quality 25%, unresolved risk 20% (inverted).",
    ]


def _assumptions(coverage: ScanCoverage) -> list[str]:
    last: str = coverage.last_issue.isoformat() if coverage.last_issue else "n/a"
    return [
        f"The Gazette scan is current to the issue of {last}; expirations appear about eight weeks after the anniversary.",
        "PatentsView bibliographic data ends with grants of 2021-09-28 and claims with grants of October 2019.",
        "Patent term adjustment is not available in public tables, so end-of-term dates are estimates.",
    ]


def _quality(ops_enabled: bool, outages: list[str], flow: FlowCounts) -> list[str]:  # noqa: FBT001
    items: list[str] = [
        "Official Gazette notices are the USPTO's own publication (grade A).",
        "EPO OPS cross-check: "
        + (
            "used"
            if ops_enabled
            else "not configured for this run, so each status rests on one official source"
        ),
    ]
    if outages:
        items.append(f"Sources unavailable during the run: {', '.join(sorted(set(outages)))}.")
    if flow.not_analysed:
        items.append(
            f"{flow.not_analysed} eligible candidates were not analysed because of the analysis cap."
        )
    return items


def _limitations(flow: FlowCounts, max_candidates: int, ops_enabled: bool) -> list[str]:  # noqa: FBT001
    items: list[str] = [
        "US patents only; nothing here speaks to other countries.",
        "Screening only. Related patents, design patents and trade dress may still cover a product.",
        "A lapsed patent can be reinstated later; intervening rights protect only use that began during the lapse.",
        "Terminal disclaimers are checked only where PatentsView records them.",
    ]
    if flow.analysed < max_candidates:
        items.append(
            f"Fewer than {max_candidates} candidates survived the evidence and screening checks."
        )
    if not ops_enabled:
        items.append(
            "No independent second source for status; the EPO OPS registration was pending."
        )
    return items
