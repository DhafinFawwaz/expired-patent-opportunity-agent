from dataclasses import dataclass
from datetime import date

from patentic.adapters.bigquery import BigQueryGateway
from patentic.adapters.fixtures import FixtureCase
from patentic.adapters.og_notices import OgIndexer
from patentic.adapters.ops_legal import OpsLegalSource
from patentic.config.settings import Settings
from patentic.domain.scoring import ScoringWeights
from patentic.domain.screening import CpcSets, PowerTerms
from patentic.llm.calls import LlmCaller


@dataclass(frozen=True)
class Deps:
    settings: Settings
    og: OgIndexer
    bq: BigQueryGateway
    ops: OpsLegalSource
    llm: LlmCaller
    weights: ScoringWeights
    cpc: CpcSets
    power: PowerTerms
    today: date
    fixtures: tuple[FixtureCase, ...] = ()
    render: bool = False
