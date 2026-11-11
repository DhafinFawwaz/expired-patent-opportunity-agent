import re
from collections import Counter
from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel

from patentic.adapters.base import PatentRecord
from patentic.domain.screening import CpcSets, PowerTerms, is_core_hit, tier1_rejects

MAX_ADDED: Final[int] = 10
MAX_TERMS: Final[int] = 15
SAMPLE_TITLES: Final[int] = 3
NEIGHBOURS: Final[int] = 8
_CPC: Final[re.Pattern[str]] = re.compile(r"^([A-H]\d{2}[A-Z])(\d{1,4})?(?:/(\d{0,6}))?$")
_TERM: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z -]{2,30}$")


class RejectedCode(BaseModel):
    code: str
    reason: str


class SearchScope(BaseModel):
    prefixes: list[str]
    core: list[str]
    added: list[str] = []
    already_covered: list[str] = []
    rejected: list[RejectedCode] = []
    exclusion_terms: list[str] = []


class CodeProbe(BaseModel):
    code: str
    matches: int
    passing: int
    sample_titles: list[str] = []


class Neighbour(BaseModel):
    group: str
    co_occurring: int
    new_patents: int
    sample_title: str


class ProbeReport(BaseModel):
    round: int
    baseline_hits: int
    scoped_hits: int
    added: list[CodeProbe] = []
    neighbours: list[Neighbour] = []
    rejected: list[RejectedCode] = []


def normalise_cpc(raw: str) -> str | None:
    # Models write codes as "A47L 13/00 (Cleaning implements)"; "/00" means the whole main group.
    text: str = re.sub(r"\(.*?\)", "", raw).replace(" ", "").upper()
    found: re.Match[str] | None = _CPC.match(text)
    if found is None or found[2] is None:
        return None
    sub, group, subgroup = found[1], found[2], found[3]
    if not subgroup or set(subgroup) == {"0"}:
        return f"{sub}{group}/"
    return f"{sub}{group}/{subgroup}"


def allowed_subclasses(sets: CpcSets) -> list[str]:
    return sorted({p[:4] for p in [*sets.core, *sets.supporting]})


def resolve_scope(
    cpc_codes: Sequence[str], exclusion_terms: Sequence[str], sets: CpcSets, power: PowerTerms
) -> SearchScope:
    known: list[str] = [*sets.core, *sets.supporting]
    subclasses: list[str] = allowed_subclasses(sets)
    added: list[str] = []
    covered: list[str] = []
    rejected: list[RejectedCode] = []
    for raw in cpc_codes:
        code: str | None = normalise_cpc(raw)
        if code is None:
            rejected.append(RejectedCode(code=raw, reason="not a CPC main group or subgroup"))
        elif code[:4] not in subclasses:
            rejected.append(
                RejectedCode(
                    code=raw, reason=f"outside the subclasses searched ({', '.join(subclasses)})"
                )
            )
        elif tier1_rejects([code], sets):
            rejected.append(RejectedCode(code=raw, reason="a powered co-class the screen removes"))
        elif any(code.startswith(p) for p in known):
            covered.append(code)
        elif code in added:
            continue
        elif len(added) >= MAX_ADDED:
            rejected.append(RejectedCode(code=raw, reason=f"more than {MAX_ADDED} new codes"))
        else:
            added.append(code)
    existing: set[str] = {t.lower() for t in [*power.terms, *power.case_sensitive_terms]}
    terms: list[str] = []
    for raw in exclusion_terms:
        term: str = raw.strip().lower()
        if _TERM.match(term) and term not in existing and term not in terms:
            terms.append(term)
    return SearchScope(
        prefixes=[*known, *added],
        core=[*sets.core, *added],
        added=added,
        already_covered=list(dict.fromkeys(covered)),
        rejected=rejected,
        exclusion_terms=terms[:MAX_TERMS],
    )


def scoped_sets(sets: CpcSets, scope: SearchScope | None) -> CpcSets:
    return sets if scope is None else sets.model_copy(update={"core": scope.core})


def plan_terms(power: PowerTerms, scope: SearchScope | None) -> PowerTerms:
    terms: list[str] = scope.exclusion_terms if scope else []
    return PowerTerms(terms=terms, manual_exceptions=power.manual_exceptions)


def _main_group(code: str) -> str:
    return code.split("/", 1)[0] + "/"


def _is_indexing(group: str) -> bool:
    # CPC 2000-series groups are indexing codes, not places a patent is classified.
    digits: str = group[4:].rstrip("/")
    return digits.isdigit() and int(digits) >= 2000  # noqa: PLR2004


def probe_scope(
    records: Sequence[PatentRecord], scope: SearchScope, sets: CpcSets, round_no: int
) -> ProbeReport:
    scoped: CpcSets = scoped_sets(sets, scope)

    def passing(r: PatentRecord, within: CpcSets) -> bool:
        return is_core_hit(r.cpc_codes, within) and not tier1_rejects(r.cpc_codes, within)

    baseline: list[PatentRecord] = [r for r in records if passing(r, sets)]
    probes: list[CodeProbe] = []
    for code in scope.added:
        matched: list[PatentRecord] = [
            r for r in records if any(c.startswith(code) for c in r.cpc_codes)
        ]
        good: list[PatentRecord] = [r for r in matched if not tier1_rejects(r.cpc_codes, scoped)]
        probes.append(
            CodeProbe(
                code=code,
                matches=len(matched),
                passing=len(good),
                sample_titles=[r.title for r in good[:SAMPLE_TITLES]],
            )
        )
    subclasses: list[str] = allowed_subclasses(sets)
    found: set[str] = {r.patent.key for r in baseline}
    counts: Counter[str] = Counter()
    for r in baseline:
        for group in {_main_group(c) for c in r.cpc_codes}:
            if group[:4] not in subclasses or _is_indexing(group) or tier1_rejects([group], sets):
                continue
            if any(group.startswith(p) or p.startswith(group) for p in scope.prefixes):
                continue
            counts[group] += 1
    neighbours: list[Neighbour] = []
    for group, n in counts.most_common(NEIGHBOURS):
        new: list[PatentRecord] = [
            r
            for r in records
            if r.patent.key not in found
            and any(c.startswith(group) for c in r.cpc_codes)
            and not tier1_rejects(r.cpc_codes, sets)
        ]
        title: str = new[0].title if new else ""
        neighbours.append(
            Neighbour(group=group, co_occurring=n, new_patents=len(new), sample_title=title)
        )
    return ProbeReport(
        round=round_no,
        baseline_hits=len(baseline),
        scoped_hits=sum(1 for r in records if passing(r, scoped)),
        added=probes,
        neighbours=neighbours,
        rejected=scope.rejected,
    )
