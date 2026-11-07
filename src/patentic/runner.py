import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pydantic
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, StateSnapshot
from pydantic import BaseModel
from rich.console import Console

from patentic.graph.build import build_graph
from patentic.graph.deps import Deps
from patentic.runlog import EventLog
from patentic.tui.prompts import AskHuman

if TYPE_CHECKING:
    from collections.abc import Iterator

    from patentic.llm.schemas import CallMeta

RunStatus = Literal["completed", "aborted", "interrupted", "validation_failed"]


def run_status(stage: object) -> RunStatus:
    if stage == "aborted":
        return "aborted"
    if stage == "validation_failed":
        return "validation_failed"
    return "completed"


def _project_models(base: type[BaseModel] = BaseModel) -> list[type[BaseModel]]:
    found: list[type[BaseModel]] = []
    for sub in base.__subclasses__():
        if sub.__module__.startswith("patentic."):
            found.append(sub)
        found.extend(_project_models(sub))
    return found


def checkpoint_serde() -> JsonPlusSerializer:
    # Register our own state models so checkpoints load without LangGraph's msgpack warning.
    return JsonPlusSerializer(allowed_msgpack_modules=list(dict.fromkeys(_project_models())))


class RunResult(BaseModel):
    thread_id: str
    status: RunStatus
    run_dir: Path
    bundle_path: str | None = None


class Runner:
    def __init__(
        self, deps: Deps, run_dir: Path, ask_human: AskHuman, console: Console, thread_id: str
    ) -> None:
        self._deps: Deps = deps
        self._run_dir: Path = run_dir
        self._ask: AskHuman = ask_human
        self._console: Console = console
        self._thread_id: str = thread_id
        self._log: EventLog = EventLog(run_dir / "events.jsonl", thread_id)
        run_dir.mkdir(parents=True, exist_ok=True)

    def run(self, inputs: dict[str, object] | None) -> RunResult:
        conn: sqlite3.Connection = sqlite3.connect(
            self._run_dir / "checkpoints.sqlite", check_same_thread=False
        )
        try:
            graph: CompiledStateGraph[Any, Any, Any, Any] = build_graph(
                self._deps, SqliteSaver(conn, serde=checkpoint_serde())
            )
            return self._drive(graph, inputs)
        finally:
            conn.close()

    def _drive(
        self, graph: CompiledStateGraph[Any, Any, Any, Any], inputs: dict[str, object] | None
    ) -> RunResult:
        config: RunnableConfig = {"configurable": {"thread_id": self._thread_id}}
        payload: dict[str, object] | Command[Any] | None = inputs
        while True:
            snapshot: StateSnapshot = graph.get_state(config)
            if payload is None and snapshot.interrupts:
                payload = Command(resume=self._ask(dict(snapshot.interrupts[0].value)))
            try:
                self._stream(graph, payload, config)
            except pydantic.ValidationError as exc:
                self._console.print(
                    f"[red]That answer was not valid:[/red] {exc.errors()[0]['msg']}"
                )
                self._log.write({"stage": "gate", "event": "invalid_answer"})
                payload = None
                continue
            snapshot = graph.get_state(config)
            if not snapshot.interrupts:
                break
            payload = None
        values: dict[str, Any] = snapshot.values
        self._write_cost(values)
        status: RunStatus = run_status(values.get("stage"))
        self._log.write({"stage": "run", "event": status})
        return RunResult(
            thread_id=self._thread_id,
            status=status,
            run_dir=self._run_dir,
            bundle_path=values.get("bundle_path"),
        )

    def _stream(
        self,
        graph: CompiledStateGraph[Any, Any, Any, Any],
        payload: dict[str, object] | Command[Any] | None,
        config: RunnableConfig,
    ) -> None:
        chunks: Iterator[Any] = graph.stream(
            payload, config, stream_mode=["updates", "custom"], durability="sync"
        )
        for mode, chunk in chunks:
            if mode == "custom" and isinstance(chunk, dict):
                self._log.write(chunk)
                self._console.print(_describe(chunk))
            elif mode == "updates" and isinstance(chunk, dict):
                for node in chunk:
                    if node != "__interrupt__":
                        self._log.write({"stage": node, "event": "done"})
                        self._console.print(f"[green]done[/green] {node}")

    def _write_cost(self, values: dict[str, Any]) -> None:
        calls: list[CallMeta] = values.get("calls", [])
        cost: dict[str, object] = {
            "llm_calls": len(calls),
            "fallback_calls": sum(1 for c in calls if c.method == "fallback"),
            "tokens_in": sum(c.tokens_in for c in calls),
            "tokens_out": sum(c.tokens_out for c in calls),
            "cost_usd": round(sum(c.cost_usd for c in calls), 6),
            "models": sorted({c.model for c in calls}),
            "bigquery_bytes_total": self._deps.bq.ledger.total(),
            "note": "Free deployments report zero cost; that comes from the route, not the model.",
        }
        (self._run_dir / "cost.json").write_text(json.dumps(cost, indent=2))


def _describe(chunk: dict[str, object]) -> str:
    stage: object = chunk.get("stage", "")
    event: object = chunk.get("event", "")
    rest: str = ", ".join(f"{k}={v}" for k, v in chunk.items() if k not in {"stage", "event"})
    colour: str = "red" if event == "outage" else "cyan"
    return f"[{colour}]{stage}[/{colour}] {event} {rest}".rstrip()
