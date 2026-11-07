from datetime import date
from typing import Literal

from pydantic import BaseModel

from patentic.domain.status_rules import TERM_YEARS, add_years


class TermEstimate(BaseModel):
    end: date
    pta_known: Literal[False] = False
    basis: str


def estimate_term_end(filing_date: date, earliest_us_nonprovisional: date | None) -> TermEstimate:
    if earliest_us_nonprovisional is not None and earliest_us_nonprovisional < filing_date:
        return TermEstimate(
            end=add_years(earliest_us_nonprovisional, TERM_YEARS),
            basis=f"20 years from the earliest US filing, {earliest_us_nonprovisional}",
        )
    return TermEstimate(
        end=add_years(filing_date, TERM_YEARS),
        basis=f"20 years from filing, {filing_date}; patent term adjustment unknown",
    )
