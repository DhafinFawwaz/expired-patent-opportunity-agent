import re
from collections.abc import Sequence

from pydantic import BaseModel

from patentic.config.loaders import read_yaml


class CpcSets(BaseModel):
    core: list[str]
    supporting: list[str]
    household_index: list[str]
    excluded_coclass: list[str]
    exclusion_exceptions: list[str] = []


class PowerTerms(BaseModel):
    terms: list[str]
    case_sensitive_terms: list[str] = []
    manual_exceptions: list[str] = []


def load_cpc_sets() -> CpcSets:
    return CpcSets.model_validate(read_yaml("cpc_sets.yaml"))


def load_power_terms() -> PowerTerms:
    return PowerTerms.model_validate(read_yaml("power_terms.yaml"))


def _matches(code: str, prefixes: Sequence[str]) -> bool:
    return any(code.startswith(prefix) for prefix in prefixes)


def is_core_hit(cpc_codes: Sequence[str], sets: CpcSets) -> bool:
    if any(_matches(code, sets.core) for code in cpc_codes):
        return True
    supporting: bool = any(_matches(code, sets.supporting) for code in cpc_codes)
    household: bool = any(_matches(code, sets.household_index) for code in cpc_codes)
    return supporting and household


def tier1_rejects(cpc_codes: Sequence[str], sets: CpcSets) -> list[str]:
    hits: list[str] = []
    for code in cpc_codes:
        if _matches(code, sets.exclusion_exceptions):
            continue
        hits.extend(p for p in sets.excluded_coclass if code.startswith(p) and p not in hits)
    return hits


def tier2_power_hits(independent_claim_texts: Sequence[str], terms: PowerTerms) -> list[str]:
    hits: list[str] = []
    for text in independent_claim_texts:
        cleaned: str = text
        for phrase in terms.manual_exceptions:
            cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.IGNORECASE)
        for term in terms.terms:
            if term not in hits and re.search(rf"\b{re.escape(term)}\b", cleaned, re.IGNORECASE):
                hits.append(term)
        for term in terms.case_sensitive_terms:
            if term not in hits and re.search(rf"\b{re.escape(term)}\b", cleaned):
                hits.append(term)
    return hits
