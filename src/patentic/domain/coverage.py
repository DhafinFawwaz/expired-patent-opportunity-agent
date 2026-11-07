from datetime import date, timedelta
from typing import Final

from pydantic import BaseModel

# The Gazette is weekly, so a scan is current when its last issue is under a week old.
CURRENT_WITHIN: Final[timedelta] = timedelta(days=7)


class ScanCoverage(BaseModel):
    weeks_fetched: int
    first_issue: date | None = None
    last_issue: date | None = None
    missing_weeks: list[date] = []
    as_of: date | None = None

    def covers_after(self, d: date) -> bool:
        if self.last_issue is None or self.last_issue < d:
            return False
        if self.as_of is not None and self.as_of - self.last_issue > CURRENT_WITHIN:
            return False
        return not any(d <= week <= self.last_issue for week in self.missing_weeks)
