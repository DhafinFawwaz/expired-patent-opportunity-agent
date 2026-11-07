import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from patentic.cli import app
from patentic.runlog import EventLog, redact

ROOT: Path = Path(__file__).parents[2]
RUNNER: CliRunner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATENTIC_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("PATENTIC_CACHE_DIR", str(tmp_path / "cache"))


def run_dir(tmp_path: Path, thread: str) -> Path:
    return tmp_path / "outputs" / "runs" / thread


def test_demo_runs_offline_to_completion(tmp_path: Path) -> None:
    result: Result = RUNNER.invoke(
        app,
        [
            "demo",
            "--no-llm",
            "--decisions",
            str(ROOT / "fixtures/decisions/approve-all.yaml"),
            "--thread-id",
            "run-demo",
        ],
    )
    assert result.exit_code == 0, result.output
    folder: Path = run_dir(tmp_path, "run-demo")
    events: list[dict[str, object]] = [
        json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()
    ]
    assert any(e.get("stage") == "rank" for e in events)
    cost: dict[str, object] = json.loads((folder / "cost.json").read_text())
    assert cost["cost_usd"] == 0.0
    assert json.loads((folder / "run.json").read_text())["mode"] == "demo"


def test_run_non_interactive_with_simulated_outages(tmp_path: Path) -> None:
    result: Result = RUNNER.invoke(
        app,
        [
            "run",
            "--request-file",
            str(ROOT / "fixtures/requests/demo-cleaning-tools.yaml"),
            "--no-llm",
            "--offline",
            "--simulate-outage",
            "og",
            "--decisions",
            str(ROOT / "fixtures/decisions/approve-all.yaml"),
            "--thread-id",
            "run-outage",
        ],
    )
    assert result.exit_code == 0, result.output
    events: str = (run_dir(tmp_path, "run-outage") / "events.jsonl").read_text()
    assert '"outage"' in events
    assert "outage" in result.output.lower()


def test_redact_hides_secrets_and_long_snippets() -> None:
    cleaned: object = redact(
        {"api_key": "sk-123", "nested": {"Authorization": "Bearer x"}, "raw_snippet": "y" * 500}
    )
    assert isinstance(cleaned, dict)
    assert cleaned["api_key"] == "[redacted]"
    assert cleaned["nested"] == {"Authorization": "[redacted]"}
    assert len(str(cleaned["raw_snippet"])) == 200


def test_events_log_writes_redacted_lines(tmp_path: Path) -> None:
    log: EventLog = EventLog(tmp_path / "events.jsonl", "t1")
    log.write({"stage": "plan", "event": "x", "token": "secret"})
    line: dict[str, object] = json.loads((tmp_path / "events.jsonl").read_text())
    assert line["token"] == "[redacted]"
    assert line["thread_id"] == "t1"
    assert "ts" in line
