from datetime import date
from pathlib import Path

from patentic.llm.schemas import TechnicalContext, TechnicalSummary
from patentic.replay import Provenance, Recorded, ReplayCaller, load_recorded, pack, unpack


def _provenance() -> Provenance:
    return Provenance(
        thread_id="run-real-1",
        today=date(2026, 11, 7),
        request={"technology_category": "cleaning tools", "lapse_window_weeks": 104},
        commit="abc1234",
        bigquery_bytes=44_000_000_000,
        candidates=[("US8646606", "reinstated")],
    )


def test_pack_then_unpack_restores_cache_files(tmp_path: Path) -> None:
    cache: Path = tmp_path / "cache"
    (cache / "http" / "og").mkdir(parents=True)
    (cache / "bq" / "queries").mkdir(parents=True)
    (cache / "http" / "og" / "a.json").write_text('{"url": "u"}')
    (cache / "bq" / "queries" / "b.json").write_text("[]")
    (cache / "ops").mkdir()
    (cache / "ops" / "skip.json").write_text("{}")
    out: Path = tmp_path / "replay"
    pack(cache, out, _provenance(), Recorded())
    restored: Path = tmp_path / "restored"
    loaded: Provenance = unpack(out, restored)
    assert loaded == _provenance()
    assert (restored / "http" / "og" / "a.json").read_text() == '{"url": "u"}'
    assert (restored / "bq" / "queries" / "b.json").read_text() == "[]"
    assert not (restored / "ops").exists()
    assert sorted(p.name for p in out.iterdir()) == ["cache.json.gz", "llm.json", "provenance.json"]


def _technical() -> TechnicalSummary:
    return TechnicalSummary(
        summary="A flat mop.",
        mechanism="A trigger releases the cloth.",
        key_claim_elements=["trigger"],
        implementation_unknowns=[],
        powered="non_powered",
        evidence_ids=["ev1"],
        quotes=[],
    )


def test_replay_caller_returns_recorded_answers_then_falls_back() -> None:
    recorded: Recorded = Recorded(
        technical={"US-8800092": _technical()}, prose={"methodology": "Recorded text."}
    )
    llm: ReplayCaller = ReplayCaller(recorded)
    ctx: TechnicalContext = TechnicalContext(
        patent_key="US-8800092",
        title="Mop",
        abstract_or_first_claim="1. A mop.",
        text="1. A mop.",
        evidence_ids=["ev1"],
    )
    summary, meta = llm.technical(ctx)
    assert summary == _technical()
    assert meta.model == "replay"
    other, other_meta = llm.technical(ctx.model_copy(update={"patent_key": "US-1"}))
    assert other_meta.method == "fallback"
    assert other.powered == "unclear"
    section, _ = llm.prose("methodology", {"fallback": "x"}, 100)
    assert section.text == "Recorded text."


def test_pack_stores_recorded_answers(tmp_path: Path) -> None:
    recorded: Recorded = Recorded(prose={"methodology": "Recorded text."})
    pack(tmp_path / "cache", tmp_path / "replay", _provenance(), recorded)
    assert load_recorded(tmp_path / "replay") == recorded
