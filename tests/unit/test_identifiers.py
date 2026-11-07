import pytest

from patentic.domain.identifiers import (
    IdentifierError,
    PatentId,
    format_application_number,
    parse_application_number,
    parse_patent_number,
)


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("7,653,958", "US-7653958"),
        ("US-7653958-B2", "US-7653958"),
        ("US7653958B2", "US-7653958"),
        ("07653958", "US-7653958"),
        ("RE.46,721", "US-RE46721"),
        ("RE. 47,917", "US-RE47917"),
        ("D812345", "US-D812345"),
        ("PP12345", "US-PP12345"),
        ("US-RE46721-E", "US-RE46721"),
    ],
)
def test_patent_keys(raw: str, key: str) -> None:
    assert parse_patent_number(raw).key == key


def test_canonical_keeps_kind_when_known() -> None:
    assert parse_patent_number("US-7653958-B2").canonical == "US-7653958-B2"
    assert parse_patent_number("RE.46,721").canonical == "US-RE46721"


def test_display_format() -> None:
    assert parse_patent_number("US7653958B2").display == "7,653,958"
    assert parse_patent_number("RE. 47,917").display == "RE47,917"


@pytest.mark.parametrize(
    ("raw", "eligible"),
    [("7,653,958", True), ("RE.46,721", True), ("D812345", False), ("PP12345", False)],
)
def test_maintenance_eligibility(raw: str, eligible: bool) -> None:
    assert parse_patent_number(raw).maintenance_eligible is eligible


@pytest.mark.parametrize("raw", ["", "abc", "US-2012048766-A1", "US20120048766A1"])
def test_bad_patent_numbers_raise(raw: str) -> None:
    with pytest.raises(IdentifierError):
        parse_patent_number(raw)


def test_patent_and_application_not_inferred_from_magnitude() -> None:
    assert parse_patent_number("12000001").number == 12000001


@pytest.mark.parametrize(
    ("raw", "compact"),
    [("13/031,042", "13031042"), ("13031042", "13031042"), ("07/653,958", "07653958")],
)
def test_application_numbers(raw: str, compact: str) -> None:
    assert parse_application_number(raw) == compact


def test_application_number_display() -> None:
    assert format_application_number("13031042") == "13/031,042"


def test_bad_application_number_raises() -> None:
    with pytest.raises(IdentifierError):
        parse_application_number("13/031")


def test_patent_id_is_hashable_and_frozen() -> None:
    a: PatentId = parse_patent_number("7,653,958")
    b: PatentId = parse_patent_number("US7653958B2")
    assert a.key == b.key
    assert {a.key: 1}[b.key] == 1
