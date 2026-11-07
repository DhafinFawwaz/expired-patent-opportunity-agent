"""Pack a finished live run and its cache into fixtures/replay/."""

import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from langgraph.checkpoint.sqlite import SqliteSaver

from patentic.adapters.bigquery import BytesLedger
from patentic.config.settings import Settings
from patentic.replay import REPLAY_DIR, Provenance, Recorded, pack
from patentic.report.bundle import ReportBundle
from patentic.runner import checkpoint_serde

if TYPE_CHECKING:
    from langgraph.checkpoint.base import CheckpointTuple

    from patentic.graph.state import Candidate


def recorded_answers(run_dir: Path, bundle: ReportBundle) -> Recorded:
    with sqlite3.connect(run_dir / "checkpoints.sqlite") as conn:
        saver: SqliteSaver = SqliteSaver(conn, serde=checkpoint_serde())
        final: CheckpointTuple | None = saver.get_tuple(
            {"configurable": {"thread_id": run_dir.name}}
        )
    if final is None:
        msg = f"no checkpoint in {run_dir}"
        raise SystemExit(msg)
    values: dict[str, object] = final.checkpoint["channel_values"]
    candidates: dict[str, Candidate] = values.get("candidates", {})  # type: ignore[assignment]
    return Recorded(
        plan=values.get("plan"),  # type: ignore[arg-type]
        technical={k: c.technical for k, c in candidates.items() if c.technical},
        opportunity={k: c.opportunity for k, c in candidates.items() if c.opportunity},
        prose=dict(bundle.prose),
    )


def main(thread_id: str) -> None:
    settings: Settings = Settings()
    run_dir: Path = settings.patentic_outputs_dir / "runs" / thread_id
    config: dict[str, object] = json.loads((run_dir / "run.json").read_text())
    bundle: ReportBundle = ReportBundle.model_validate_json((run_dir / "bundle.json").read_text())
    commit: str = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    provenance: Provenance = Provenance(
        thread_id=thread_id,
        today=date.fromisoformat(str(config["today"])),
        request=dict(config["request"]),  # type: ignore[call-overload]
        commit=commit,
        bigquery_bytes=BytesLedger(settings.patentic_outputs_dir / "bytes-ledger.json").total(),
        candidates=[(c.key, c.status.label) for c in bundle.candidates],
    )
    pack(settings.patentic_cache_dir, REPLAY_DIR, provenance, recorded_answers(run_dir, bundle))
    size: int = (REPLAY_DIR / "cache.json.gz").stat().st_size
    print(f"wrote {REPLAY_DIR} ({size:,} bytes, {len(provenance.candidates)} candidates)")  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1])
