import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from patentic.cli import app
from patentic.replay import REPLAY_DIR, Provenance

ROOT: Path = Path(__file__).parents[2]


def test_replay_reproduces_the_real_run_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("PATENTIC_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("PATENTIC_CACHE_DIR", str(tmp_path / "cache"))
    expected: Provenance = Provenance.model_validate_json(
        (REPLAY_DIR / "provenance.json").read_text()
    )
    result: Result = CliRunner().invoke(
        app,
        [
            "run",
            "--replay",
            "--decisions",
            "fixtures/decisions/approve-all.yaml",
            "--thread-id",
            "run-replay",
        ],
    )
    assert result.exit_code == 0, result.output
    run_dir: Path = tmp_path / "outputs" / "runs" / "run-replay"
    bundle: dict[str, list[dict[str, object]]] = json.loads((run_dir / "bundle.json").read_text())
    got: list[tuple[str, str]] = [
        (str(c["key"]), str(c["status"]["label"]))  # type: ignore[index]
        for c in bundle["candidates"]
    ]
    assert got == [tuple(c) for c in expected.candidates]
    assert json.loads((run_dir / "validation.json").read_text())["ok"] is True
