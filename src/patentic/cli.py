import json
import secrets
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

import typer
import yaml
from rich.console import Console

from patentic.adapters.http import utc_now
from patentic.config.settings import Settings
from patentic.domain.request import ResearchRequest
from patentic.runner import Runner, RunResult
from patentic.schemas_export import export_schemas
from patentic.tui.prompts import AskHuman, StopRunError, rich_ask_human, scripted_ask_human
from patentic.wiring import Outage, make_deps

app: typer.Typer = typer.Typer(no_args_is_help=True, add_completion=False)
console: Console = Console()
DEMO_REQUEST: Path = Path("fixtures") / "requests" / "demo-cleaning-tools.yaml"


def new_thread_id(slug: str) -> str:
    return f"run-{utc_now():%Y%m%d}-{slug}-{secrets.token_hex(3)}"


def _load_yaml(path: Path) -> Any:  # noqa: ANN401  # YAML is untyped until validated
    return yaml.safe_load(path.read_text())


def _ask(decisions: Path | None) -> AskHuman:
    if decisions is None:
        return rich_ask_human(console)
    loaded: object = _load_yaml(decisions)
    items: list[dict[str, object]] = [dict(d) for d in loaded] if isinstance(loaded, list) else []
    return scripted_ask_human(items)


def _execute(
    run_config: dict[str, Any], thread_id: str, decisions: Path | None, *, resume: bool
) -> RunResult:
    settings: Settings = Settings()
    run_dir: Path = settings.patentic_outputs_dir / "runs" / thread_id
    deps = make_deps(
        settings,
        demo=run_config["mode"] == "demo",
        no_llm=bool(run_config["no_llm"]),
        offline=bool(run_config["offline"]),
        simulate_outage=run_config.get("simulate_outage"),
        today=date.fromisoformat(run_config["today"]) if run_config.get("today") else None,
    )
    if not resume:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(json.dumps(run_config, indent=2, default=str))
    console.print(f"Run [bold]{thread_id}[/bold] in {run_dir}")
    runner: Runner = Runner(deps, run_dir, _ask(decisions), console, thread_id)
    inputs: dict[str, object] | None = (
        None if resume else {"request": ResearchRequest(**run_config["request"])}
    )
    try:
        result: RunResult = runner.run(inputs)
    except StopRunError:
        console.print(f"Stopped. Resume with: patentic resume {thread_id}")
        raise typer.Exit(130) from None
    console.print(f"Run {result.status}. Logs: {run_dir / 'events.jsonl'}")
    return result


DecisionsOpt = Annotated[
    Path | None, typer.Option(help="YAML file of scripted answers for the two gates")
]
ThreadOpt = Annotated[
    str | None, typer.Option(help="Use this thread id instead of a generated one")
]
NoLlmOpt = Annotated[
    bool, typer.Option("--no-llm", help="Run without a model; every model step uses its template")
]


@app.command()
def run(
    request_file: Annotated[Path, typer.Option(help="Research request YAML")] = DEMO_REQUEST,
    decisions: DecisionsOpt = None,
    simulate_outage: Annotated[
        Literal["og", "bigquery", "ops"] | None, typer.Option(help="Make one source fail")
    ] = None,
    og_weeks: Annotated[int | None, typer.Option(help="Gazette weeks to scan")] = None,
    offline: Annotated[bool, typer.Option("--offline", help="Use cached data only")] = False,
    no_llm: NoLlmOpt = False,
    thread_id: ThreadOpt = None,
) -> None:
    """Run the pipeline on a research request."""
    request: dict[str, object] = dict(_load_yaml(request_file))
    if og_weeks:
        request["lapse_window_weeks"] = og_weeks
    outage: Outage | None = simulate_outage
    config: dict[str, Any] = {
        "mode": "live",
        "request": request,
        "no_llm": no_llm,
        "offline": offline,
        "simulate_outage": outage,
        "created": utc_now().isoformat(),
        "today": date.today().isoformat(),  # noqa: DTZ011
    }
    _execute(config, thread_id or new_thread_id("live"), decisions, resume=False)


@app.command()
def demo(
    decisions: DecisionsOpt = None, no_llm: NoLlmOpt = False, thread_id: ThreadOpt = None
) -> None:
    """Run the six synthetic fixtures through the same pipeline, offline."""
    config: dict[str, Any] = {
        "mode": "demo",
        "request": dict(_load_yaml(DEMO_REQUEST)),
        "no_llm": no_llm,
        "offline": True,
        "simulate_outage": None,
        "created": utc_now().isoformat(),
    }
    _execute(config, thread_id or new_thread_id("demo"), decisions, resume=False)


@app.command()
def resume(thread_id: str, decisions: DecisionsOpt = None) -> None:
    """Continue a stopped run from its last checkpoint."""
    run_dir: Path = Settings().patentic_outputs_dir / "runs" / thread_id
    config: dict[str, Any] = json.loads((run_dir / "run.json").read_text())
    _execute(config, thread_id, decisions, resume=True)


@app.command()
def cost(thread_id: str) -> None:
    """Print the cost record of a run."""
    path: Path = Settings().patentic_outputs_dir / "runs" / thread_id / "cost.json"
    console.print_json(path.read_text())


@app.command()
def schemas(out_dir: Annotated[Path, typer.Option()] = Path("schemas")) -> None:
    """Write JSON Schemas for the data models."""
    for path in export_schemas(out_dir):
        console.print(str(path))
