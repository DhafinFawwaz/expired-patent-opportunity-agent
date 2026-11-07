import os
from datetime import date
from pathlib import Path

import pytest

from patentic.adapters.base import PatentRecord
from patentic.adapters.bigquery import BigQueryGateway, BytesLedger, GoogleQueryRunner


@pytest.mark.live
def test_live_discovery_small_window(tmp_path: Path) -> None:
    project: str | None = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if os.environ.get("PATENTIC_LIVE") != "1" or not project:
        pytest.skip("set PATENTIC_LIVE=1 and GOOGLE_CLOUD_PROJECT")
    runner: GoogleQueryRunner = GoogleQueryRunner(project, os.environ.get("GOOGLE_CLOUD_ACCOUNT"))
    ledger: BytesLedger = BytesLedger(tmp_path / "ledger.json")
    gw: BigQueryGateway = BigQueryGateway(runner, tmp_path, ledger)
    records: list[PatentRecord] = gw.discover(["A47L13/"], date(2016, 11, 1), date(2016, 12, 31))
    assert len(records) >= 5
    assert ledger.total() < 3_000_000_000
