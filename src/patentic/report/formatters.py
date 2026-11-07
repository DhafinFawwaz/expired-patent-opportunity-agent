from datetime import date
from typing import Final

from patentic.domain.identifiers import parse_patent_number

_STATUS_TEXT: Final[dict[str, str]] = {
    "expired_nonpayment": "Expired (nonpayment)",
    "reinstated": "Reinstated",
    "in_grace_period": "In grace period",
    "petition_pending": "Petition pending",
    "expired_end_of_term": "Expired (end of term)",
    "conflicting": "Conflicting evidence",
    "in_force": "In force",
    "not_subject_to_maintenance_fees": "No maintenance fees (design or plant)",
    "unknown": "Unknown",
}
_EVENT_TEXT: Final[dict[str, str]] = {
    "grant": "Granted",
    "fee_paid": "Maintenance fee paid",
    "reminder": "Fee reminder mailed",
    "surcharge": "Late surcharge paid",
    "lapse": "Listed as expired for nonpayment",
    "petition_filed": "Petition to accept late fee filed",
    "petition_granted": "Petition granted",
    "petition_denied": "Petition denied",
    "reinstated": "Reinstated after late fee accepted",
    "defective_payment": "Defective payment",
    "terminal_disclaimer": "Terminal disclaimer",
    "outage": "Source unavailable",
}
_SOURCE_TEXT: Final[dict[str, str]] = {
    "og_notice": "USPTO Official Gazette",
    "ops": "EPO OPS (INPADOC)",
    "odp": "USPTO maintenance fee file",
    "bigquery": "BigQuery PatentsView",
    "fixture": "Synthetic fixture",
    "manual": "Manual observation (Google Patents)",
}


def fmt_patent(key: str) -> str:
    return f"US {parse_patent_number(key).display}"


def fmt_date(value: date | None) -> str:
    return value.isoformat() if value else "n/a"


def fmt_score(value: float | None) -> str:
    return f"{value:.1f}" if value is not None else "n/a"


def fmt_status(label: str) -> str:
    return _STATUS_TEXT.get(label, label)


def fmt_confidence(confidence: str) -> str:
    return confidence.replace("_", " ")


def fmt_event(event_type: str, effective: date | None) -> str:
    text: str = _EVENT_TEXT.get(event_type, event_type)
    return f"{text} (effective {effective.isoformat()})" if effective else text


def fmt_source(source: str) -> str:
    return _SOURCE_TEXT.get(source, source)
