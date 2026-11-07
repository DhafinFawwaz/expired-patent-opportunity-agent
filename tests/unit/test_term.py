from datetime import date

from patentic.domain.term import TermEstimate, estimate_term_end


def test_estimate_term_end_pta_unknown() -> None:
    estimate: TermEstimate = estimate_term_end(date(2004, 3, 1), None)
    assert estimate.end == date(2024, 3, 1)
    assert estimate.pta_known is False


def test_term_runs_from_earliest_us_nonprovisional() -> None:
    estimate: TermEstimate = estimate_term_end(date(2006, 5, 1), date(2003, 2, 10))
    assert estimate.end == date(2023, 2, 10)
    assert "earliest" in estimate.basis
