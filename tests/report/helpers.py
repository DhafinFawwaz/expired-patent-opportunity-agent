from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from patentic.adapters.fixtures import FixtureCase, load_fixtures
from patentic.graph.deps import Deps
from patentic.report.bundle import ReportBundle
from tests.graph.helpers import REQUEST, compile_graph, make_deps, plan_replies, run_until_interrupt
from tests.llm.fakes import scripted

ROOT: Path = Path(__file__).parents[2]
CONFIG: RunnableConfig = {"configurable": {"thread_id": "t1"}}
FIXTURES: list[FixtureCase] = load_fixtures(ROOT / "fixtures" / "synthetic")
TEMPLATES: Path = ROOT / "templates"


def demo_bundle(tmp_path: Path) -> ReportBundle:
    deps: Deps = make_deps(tmp_path, tools=scripted(*plan_replies(1)))
    settings = deps.settings.model_copy(update={"patentic_outputs_dir": tmp_path / "outputs"})
    deps = Deps(**{**deps.__dict__, "fixtures": tuple(FIXTURES), "settings": settings})
    graph = compile_graph(deps)
    run_until_interrupt(graph, {"request": REQUEST})
    run_until_interrupt(graph, Command(resume={"action": "approve"}))
    run_until_interrupt(graph, Command(resume={"action": "accept"}))
    values: dict[str, Any] = graph.get_state(CONFIG).values
    return ReportBundle.model_validate_json(Path(values["bundle_path"]).read_text())
