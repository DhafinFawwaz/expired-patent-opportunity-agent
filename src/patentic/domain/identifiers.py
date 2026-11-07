import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

Prefix = Literal["", "RE", "D", "PP", "H", "T"]

_PATENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:US)?-?(?P<prefix>RE|PP|D|H|T)?[.\s]*(?P<digits>[\d,]+)-?(?P<kind>[A-Z]\d?)?$"
)
_APPLICATION_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<series>\d{2})/?(?P<serial>\d{3},?\d{3})$"
)
_MAX_PATENT_DIGITS: Final[int] = 8


class IdentifierError(ValueError):
    pass


class PatentId(BaseModel):
    model_config = ConfigDict(frozen=True)

    country: Literal["US"] = "US"
    prefix: Prefix = ""
    number: int
    kind: str | None = None

    @property
    def key(self) -> str:
        return f"US-{self.prefix}{self.number}"

    @property
    def canonical(self) -> str:
        return f"{self.key}-{self.kind}" if self.kind else self.key

    @property
    def display(self) -> str:
        return f"{self.prefix}{self.number:,}"

    @property
    def maintenance_eligible(self) -> bool:
        return self.prefix in {"", "RE"}


def parse_patent_number(raw: str) -> PatentId:
    text: str = raw.strip().upper().replace(" ", "")
    match: re.Match[str] | None = _PATENT_RE.match(text)
    if not text or match is None:
        msg = f"not a US patent number: {raw!r}"
        raise IdentifierError(msg)
    digits: str = match["digits"].replace(",", "")
    # Pre-grant publications look like 2012048766 (11 digits); patents never exceed 8.
    if not digits or len(digits) > _MAX_PATENT_DIGITS:
        msg = f"not a US patent number: {raw!r}"
        raise IdentifierError(msg)
    prefix: Prefix = _as_prefix(match["prefix"] or "")
    return PatentId(prefix=prefix, number=int(digits), kind=match["kind"])


def parse_application_number(raw: str) -> str:
    match: re.Match[str] | None = _APPLICATION_RE.match(raw.strip())
    if match is None:
        msg = f"not a US application number: {raw!r}"
        raise IdentifierError(msg)
    return match["series"] + match["serial"].replace(",", "")


def format_application_number(compact: str) -> str:
    return f"{compact[:2]}/{compact[2:5]},{compact[5:]}"


def _as_prefix(value: str) -> Prefix:
    prefixes: dict[str, Prefix] = {"": "", "RE": "RE", "D": "D", "PP": "PP", "H": "H", "T": "T"}
    return prefixes[value]
