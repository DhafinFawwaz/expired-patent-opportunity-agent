from collections.abc import Sequence
from typing import Final, Literal

from pydantic import BaseModel

from patentic.adapters.base import PatentRecord

Relation = Literal[
    "family",
    "continuation",
    "division",
    "cip",
    "forward_citation",
    "same_assignee",
    "reissue",
    "terminal_disclaimer",
]
_LINEAGE: Final[frozenset[str]] = frozenset({"continuation", "division", "cip"})
_DECLARED: Final[dict[str, Relation]] = {
    "continuation": "continuation",
    "division": "division",
    "cip": "cip",
    "reissue": "reissue",
}


class RelatedRecord(BaseModel):
    relation: Relation
    patent_key: str
    source_field: str
    evidence: str
    status_to_verify: bool = True


def related_records(
    record: PatentRecord,
    forward_citations: Sequence[str],
    same_assignee_later: Sequence[str],
) -> list[RelatedRecord]:
    related: list[RelatedRecord] = []
    for field, keys, word in (
        ("children", record.children, "child"),
        ("parents", record.parents, "parent"),
    ):
        related.extend(
            RelatedRecord(
                relation=_relation_for(key, record.relation_types.get(key)),
                patent_key=key,
                source_field=field,
                evidence=f"{key} is listed as a {word} of {record.patent.key}",
            )
            for key in keys
        )
    related.extend(
        RelatedRecord(
            relation="forward_citation",
            patent_key=key,
            source_field="citations",
            evidence=f"{key} cites {record.patent.key}",
        )
        for key in forward_citations
    )
    related.extend(
        RelatedRecord(
            relation="same_assignee",
            patent_key=key,
            source_field="assignee",
            evidence=f"{key} is a later grant to the same assignee in the same CPC group",
        )
        for key in same_assignee_later
    )
    if record.terminal_disclaimer:
        related.append(
            RelatedRecord(
                relation="terminal_disclaimer",
                patent_key=record.patent.key,
                source_field="term_disclaimer",
                evidence="A terminal disclaimer ties this patent's term to another patent.",
            )
        )
    return related


def _relation_for(key: str, declared: str | None) -> Relation:
    if declared in _DECLARED:
        return _DECLARED[declared]
    return "reissue" if "-RE" in key else "continuation"


def related_flags(related: Sequence[RelatedRecord]) -> list[str]:
    if any(r.relation in _LINEAGE for r in related):
        return ["related_active_continuation"]
    return []
