import time
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from langchain_core.callbacks import UsageMetadataCallbackHandler

from patentic import __version__
from patentic.adapters.bigquery import BigQueryGateway, BytesLedger, GoogleQueryRunner, QueryRunner
from patentic.adapters.fixtures import load_fixtures
from patentic.adapters.http import HttpSource, outage_transport
from patentic.adapters.og_notices import OgIndexer
from patentic.adapters.ops_legal import LegalFetchError, OpsLegalSource
from patentic.config.settings import Settings
from patentic.domain.scoring import load_weights
from patentic.domain.screening import load_cpc_sets, load_power_terms
from patentic.graph.deps import Deps
from patentic.llm.calls import LlmCaller, build_models, probe_structured
from patentic.llm.null_model import NullChatModel
from patentic.replay import Recorded, ReplayCaller

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from patentic.llm.schemas import StructuredMethod

Outage = Literal["og", "bigquery", "ops"]
FIXTURES_DIR: Final[Path] = Path("fixtures") / "synthetic"
USER_AGENT: Final[str] = (
    f"patentic/{__version__} (+https://github.com/DhafinFawwaz/expired-patent-opportunity-agent)"
)


class _FailingOps:
    def fetch(self, epodoc: str) -> str:
        raise LegalFetchError(503, f"simulated outage for {epodoc}")


def make_llm(settings: Settings, *, no_llm: bool) -> LlmCaller:
    usage: UsageMetadataCallbackHandler = UsageMetadataCallbackHandler()
    if no_llm:
        null: BaseChatModel = NullChatModel()
        return LlmCaller(null, null, None, usage)
    tools, prose = build_models(settings)
    method: StructuredMethod | None = probe_structured(tools)
    return LlmCaller(tools, prose, method, usage, cache_dir=settings.patentic_cache_dir / "llm")


def make_deps(
    settings: Settings,
    *,
    demo: bool,
    no_llm: bool,
    offline: bool,
    simulate_outage: Outage | None,
    today: date | None = None,
    render: bool = False,
    recorded: Recorded | None = None,
) -> Deps:
    cache: Path = settings.patentic_cache_dir
    simulated: bool = simulate_outage == "og"
    # A simulated outage needs an empty cache, or cached pages would hide it.
    http: HttpSource = HttpSource(
        "og",
        cache / ("http-outage" if simulated else "http"),
        None,
        1.0,
        USER_AGENT,
        transport=outage_transport() if simulated else None,
        sleep=(lambda _s: None) if simulated else time.sleep,
        offline=offline and not simulated,
    )
    runner: QueryRunner | None = None
    if not (demo or offline or simulate_outage == "bigquery") and settings.google_cloud_project:
        runner = GoogleQueryRunner(settings.google_cloud_project, settings.google_cloud_account)
    bq_cache: Path = cache / ("bq-outage" if simulate_outage == "bigquery" else "bq")
    gateway: BigQueryGateway = BigQueryGateway(
        runner,
        bq_cache,
        BytesLedger(settings.patentic_outputs_dir / "bytes-ledger.json"),
        offline=runner is None,
    )
    ops: OpsLegalSource = OpsLegalSource(
        settings.epo_ops_key,
        settings.epo_ops_secret,
        cache,
        fetcher=_FailingOps() if simulate_outage == "ops" else None,
        offline=offline and simulate_outage != "ops",
    )
    if simulate_outage == "ops" and not ops.enabled:
        ops = OpsLegalSource("simulated", "simulated", cache, fetcher=_FailingOps())
    fixtures = tuple(load_fixtures(FIXTURES_DIR)) if demo else ()
    return Deps(
        settings=settings,
        og=OgIndexer(http),
        bq=gateway,
        ops=ops,
        llm=ReplayCaller(recorded) if recorded else make_llm(settings, no_llm=no_llm),
        weights=load_weights(),
        cpc=load_cpc_sets(),
        power=load_power_terms(),
        today=fixtures[0].today if fixtures else (today or date.today() + timedelta(0)),  # noqa: DTZ011
        fixtures=fixtures,
        render=render,
    )
