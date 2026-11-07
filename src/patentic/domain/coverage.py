from datetime import date, timedelta
from typing import Final

from pydantic import BaseModel

# Expiration notices appear about eight weeks after the anniversary date.
PUBLICATION_LAG: Final[timedelta] = timedelta(weeks=8)


class ScanCoverage(BaseModel):
    weeks_fetched: int
    first_issue: date | None = None
    last_issue: date | None = None
    missing_weeks: list[date] = []

    def covers_after(self, d: date) -> bool:
        if self.last_issue is None or self.last_issue < d + PUBLICATION_LAG:
            return False
        return not any(d <= week <= self.last_issue for week in self.missing_weeks)
