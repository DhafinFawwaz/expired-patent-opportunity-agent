from typing import Literal

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    technology_category: str
    intended_product: str
    jurisdiction: Literal["US"] = "US"
    commercial_constraints: list[str] = []
    max_candidates: int = Field(default=5, ge=1, le=10)
    max_recommended: int = Field(default=2, ge=0, le=2)
    lapse_window_weeks: int = Field(default=104, ge=1, le=520)
