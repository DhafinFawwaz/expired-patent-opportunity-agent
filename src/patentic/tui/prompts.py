from collections.abc import Callable, Sequence

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

AskHuman = Callable[[dict[str, object]], dict[str, object]]


class StopRunError(KeyboardInterrupt):
    pass


def scripted_ask_human(decisions: Sequence[dict[str, object]]) -> AskHuman:
    queue: list[dict[str, object]] = list(decisions)

    def ask(payload: dict[str, object]) -> dict[str, object]:
        options: object = payload.get("options", [])
        while queue:
            decision: dict[str, object] = queue.pop(0)
            if decision.get("stop"):
                raise StopRunError
            if isinstance(options, list) and decision.get("action") in options:
                return decision
        return {"action": "abort"}

    return ask


def _keys(text: str) -> list[str]:
    return [k.strip() for k in text.split(",") if k.strip()]


def rich_ask_human(console: Console) -> AskHuman:
    def ask(payload: dict[str, object]) -> dict[str, object]:
        raw_options: object = payload.get("options")
        options: list[str] = [str(o) for o in raw_options] if isinstance(raw_options, list) else []
        if payload.get("kind") == "plan_approval":
            _show_plan(console, payload)
            action: str = Prompt.ask("Plan", choices=options, default="approve", console=console)
            if action == "revise":
                return {
                    "action": action,
                    "feedback": Prompt.ask("What should change", console=console),
                }
            return {"action": action}
        _show_candidates(console, payload)
        action = Prompt.ask("Candidates", choices=options, default="accept", console=console)
        if action != "edit":
            return {"action": action}
        drop: list[str] = _keys(
            Prompt.ask("Drop (comma separated keys, blank for none)", default="", console=console)
        )
        shortlist: list[str] = _keys(
            Prompt.ask("Shortlist (up to two keys)", default="", console=console)
        )
        note_key: str = Prompt.ask(
            "Flag a candidate (key, blank to skip)", default="", console=console
        )
        flag: dict[str, str] = {}
        if note_key:
            flag[note_key] = Prompt.ask("Note", console=console)
        return {"action": "edit", "drop": drop, "shortlist": shortlist, "flag": flag}

    return ask


def _show_plan(console: Console, payload: dict[str, object]) -> None:
    plan: object = payload.get("plan", {})
    table: Table = Table(
        title=f"Research plan (revision {payload.get('revisions', 0)})", show_lines=True
    )
    table.add_column("Part")
    table.add_column("Value")
    if isinstance(plan, dict):
        for key, value in plan.items():
            table.add_row(
                str(key).replace("_", " "),
                ", ".join(map(str, value)) if isinstance(value, list) else str(value),
            )
    console.print(table)


def _show_candidates(console: Console, payload: dict[str, object]) -> None:
    table: Table = Table(title="Candidates for review")
    for column in ("Patent", "Title", "Status", "Confidence", "Score", "Recommendation", "Flags"):
        table.add_column(column)
    rows: object = payload.get("candidates", [])
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                total: object = row.get("total")
                table.add_row(
                    str(row.get("key")) + (" (synthetic)" if row.get("synthetic") else ""),
                    str(row.get("title", ""))[:48],
                    str(row.get("status")),
                    str(row.get("confidence")),
                    f"{total:.2f}" if isinstance(total, float) else "-",
                    str(row.get("recommendation") or "-"),
                    ", ".join(map(str, row.get("flags") or [])),
                )
    console.print(table)
    console.print(f"Not analysed (capacity): {payload.get('not_analysed', 0)}")
