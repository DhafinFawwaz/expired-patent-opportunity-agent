import json
import os
import subprocess
import sys
from pathlib import Path

ROOT: Path = Path(__file__).parents[2]


def patentic(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "patentic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_run_stopped_at_review_resumes_in_a_new_process(tmp_path: Path) -> None:
    env: dict[str, str] = {
        **os.environ,
        "PATENTIC_OUTPUTS_DIR": str(tmp_path / "outputs"),
        "PATENTIC_CACHE_DIR": str(tmp_path / "cache"),
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    }
    first = patentic(
        [
            "demo",
            "--no-llm",
            "--decisions",
            "fixtures/decisions/stop-at-review.yaml",
            "--thread-id",
            "run-resume",
        ],
        env,
    )
    assert first.returncode == 130, first.stdout + first.stderr
    second = patentic(
        ["resume", "run-resume", "--decisions", "fixtures/decisions/approve-all.yaml"], env
    )
    assert second.returncode == 0, second.stdout + second.stderr
    folder: Path = tmp_path / "outputs" / "runs" / "run-resume"
    stages: set[object] = {
        json.loads(line).get("stage") for line in (folder / "events.jsonl").read_text().splitlines()
    }
    assert "review" in stages
