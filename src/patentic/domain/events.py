from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

Source = Literal["og_notice", "bigquery", "ops", "odp", "fixture", "manual"]
EventType = Literal[
    "grant",
    "fee_paid",
    "reminder",
    "surcharge",
    "lapse",
    "petition_filed",
    "petition_granted",
    "petition_denied",
    "reinstated",
    "defective_payment",
    "terminal_disclaimer",
    "outage",
]
Stage = Literal[4, 8, 12]


class StatusEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: EventType
    event_date: date
    effective_date: date | None = None
    stage: Stage | None = None
    source: Source
    source_code: str
    evidence_id: str


# INPADOC re-coded US events in 2017: FPAY/REMI/SULP/REIN before, MAFP/FEPP/PRDP after.
_INPADOC: Final[dict[str, EventType]] = {
    "LAPS": "lapse",
    "STCH": "lapse",
    "FP": "lapse",
    "PRDP": "reinstated",
    "REIN": "reinstated",
    "STCK": "reinstated",
    "FPAY": "fee_paid",
    "MAFP": "fee_paid",
    "REMI": "reminder",
    "SULP": "surcharge",
    "DC": "terminal_disclaimer",
}

_USPTO_FILE: Final[dict[str, EventType]] = {
    "EXP.": "lapse",
    "EXPX": "reinstated",
    "REM.": "reminder",
    "PMFP": "petition_filed",
    "PMFG": "petition_granted",
    "PMFD": "petition_denied",
    "PMFS": "petition_denied",
}

_PEDS: Final[dict[str, EventType]] = {
    "EXP.": "lapse",
    "REIN": "reinstated",
    "REM.": "reminder",
    "DIST": "terminal_disclaimer",
    "DISQ": "terminal_disclaimer",
    "N574": "terminal_disclaimer",
    "P574": "terminal_disclaimer",
    "PMFP": "petition_filed",
    "PMFG": "petition_granted",
    "PMFD": "petition_denied",
}

_FEE_STAGE_DIGIT: Final[dict[str, Stage]] = {"1": 4, "2": 8, "3": 12}


def map_inpadoc_code(code: str, text: str = "") -> EventType | None:
    if code == "FEPP":
        return "reminder" if "reminder" in text.lower() else None
    return _INPADOC.get(code)


def map_usptofile_code(code: str) -> EventType | None:
    if code in _USPTO_FILE:
        return _USPTO_FILE[code]
    return _fee_code(code)


def map_peds_code(code: str) -> EventType | None:
    if code in _PEDS:
        return _PEDS[code]
    return _fee_code(code)


def stage_from_code(code: str) -> Stage | None:
    if len(code) == 5 and code[0] == "M" and code[2:4] == "55":  # noqa: PLR2004
        return _FEE_STAGE_DIGIT.get(code[4])
    return None


def _fee_code(code: str) -> EventType | None:
    # M1551..M3553 are payments at 3.5/7.5/11.5 years, M1554..M3556 the late surcharges;
    # the middle digit is the entity size (1 large, 2 small, 3 micro). F16x are defective payments.
    if len(code) == 5 and code[0] == "M" and code[2:4] == "55":  # noqa: PLR2004
        last: str = code[4]
        if last in {"1", "2", "3"}:
            return "fee_paid"
        if last in {"4", "5", "6"}:
            return "surcharge"
    if code.startswith("F16"):
        return "defective_payment"
    return None
