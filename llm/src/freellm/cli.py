"""``freellm`` command line.

  freellm keys [--steps]          which providers are set up, where to get free keys
  freellm init                    create llm/.env from .env.example
  freellm models [--tools] [--vision] [--pref speed] [--refresh] [--all] [--json]
  freellm ping [-n 5]             send a tiny request to the top models, record health
  freellm chat "prompt" [-m MODEL]
  freellm stats [--reset]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time

from . import config
from . import stats as stats_mod
from .catalog import discover, load_providers


def _table(rows: list[dict], cols: list[str]) -> str:
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) if rows else len(c) for c in cols}
    widths = {c: min(w, 80) for c, w in widths.items()}
    line = "  ".join(c.ljust(widths[c]) for c in cols)
    out = [line, "  ".join("-" * widths[c] for c in cols)]
    for r in rows:
        out.append("  ".join(str("" if r.get(c) is None else r.get(c))[: widths[c]].ljust(widths[c]) for c in cols))
    return "\n".join(out)


def cmd_keys(a: argparse.Namespace) -> None:
    print(f"Keys file: {config.env_file()}  ({'exists' if config.env_file().exists() else 'missing — run `freellm init`'})\n")
    rows = []
    for p in load_providers().values():
        n = len(p.keys)
        status = f"{n} key{'s' if n != 1 else ''}" if n else ("keyless OK" if p.keyless else "-")
        if n and p.resolved_api_base is None:
            status += f" (needs {', '.join(p.extra_env)})"
        rows.append({"provider": p.id, "status": status, "env var": p.key_env, "limits": p.limits, "get key": p.signup_url})
    print(_table(rows, ["provider", "status", "env var", "limits", "get key"]))
    if a.steps:
        for p in load_providers().values():
            print(f"\n## {p.name}  ->  {p.key_env}" + (f" (+ {', '.join(p.extra_env)})" if p.extra_env else ""))
            for i, s in enumerate(p.steps, 1):
                print(f"  {i}. {s}")
    else:
        print("\n`freellm keys --steps` shows step-by-step instructions for every provider.")
    print("Several keys for one provider: GROQ_API_KEY=a  GROQ_API_KEY_2=b  (or GROQ_API_KEY=a,b)")


def cmd_init(a: argparse.Namespace) -> None:
    target = config.env_file()
    example = config.home() / ".env.example"
    if target.exists():
        print(f"{target} already exists; not touching it.")
        return
    if example.exists():
        shutil.copy(example, target)
    else:
        target.write_text("".join(f"{p.key_env}=\n" for p in load_providers().values()))
    print(f"Created {target}. Paste your keys there (it is git-ignored). `freellm keys --steps` for how.")


def _fl(a: argparse.Namespace):
    from .router import FreeLLM

    return FreeLLM(refresh=getattr(a, "refresh", False), preference=getattr(a, "pref", "quality"))


def cmd_models(a: argparse.Namespace) -> None:
    if a.all:
        rows = []
        for p in load_providers().values():
            for m in discover(p):
                rows.append({"provider": p.id, "usable": p.usable, **{k: m.to_dict()[k] for k in ("model_id", "context", "tools", "vision", "source")}})
        print(_table(rows, ["provider", "usable", "model_id", "context", "tools", "vision", "source"]))
        return
    fl = _fl(a)
    if a.available:
        av = fl.available()
        rows = [
            {"#": i, "model": r.canonical, "rating": round(r.rating), "rated": r.rated,
             "working via": ", ".join(sorted(f"{d.provider.id}/{d.model.model_id}" for d in ds)),
             "tools": r.tools, "vision": r.vision, "context": r.context}
            for i, (r, ds) in enumerate(av, 1)
            if not (a.tools and r.tools is False) and not (a.vision and not r.vision)
        ]
        if a.json:
            print(json.dumps(rows, indent=1))
            return
        print(_table(rows, ["#", "model", "rating", "rated", "working via", "tools", "vision", "context"]))
        print(f"\n{len(rows)} models answered in the last check (`freellm ping` / `make check`). "
              "Sorted by LMArena rating, then name.")
        return
    ranked = fl.ranked(tools=a.tools, vision=a.vision, min_context=a.min_context)
    rows = [{"#": i, **r.as_row()} for i, r in enumerate(ranked, 1)]
    if a.json:
        print(json.dumps(rows, indent=1))
        return
    print(_table(rows, ["#", "model", "rating", "rated", "score", "providers", "keys", "tools", "vision", "context", "latency_s"]))
    print(f"\n{len(rows)} usable free models. Groups: free, free-tools, free-vision, free-fast, or any name above.")
    print("rating = LMArena text Elo (1250 = not on leaderboard). score = rating adjusted by local health stats.")


def cmd_ping(a: argparse.Namespace) -> None:
    from .router import FreeLLM

    fl = FreeLLM(refresh=a.refresh)
    router = fl.router
    for r in fl.ranked()[: a.n or None]:
        for d in r.deployments:
            t = time.time()
            try:
                resp = router.completion(
                    model=d.exact_name, messages=[{"role": "user", "content": "Reply with the single word: ok"}],
                    max_tokens=a.max_tokens, num_retries=0,
                )
                txt = (resp.choices[0].message.content or "").strip().replace("\n", " ")[:40]
                print(f"OK   {time.time() - t:5.1f}s  {d.exact_name:55}  {txt!r}")
            except Exception as e:
                print(f"FAIL {time.time() - t:5.1f}s  {d.exact_name:55}  {stats_mod.classify(e)}: {str(e)[:80]}")


def cmd_chat(a: argparse.Namespace) -> None:
    from .router import FreeLLM

    fl = FreeLLM()
    resp = fl.completion([{"role": "user", "content": " ".join(a.prompt)}], model=a.model)
    print(resp.choices[0].message.content)
    print(f"\n[served by {FreeLLM.served_by(resp)}]", file=sys.stderr)


def cmd_stats(a: argparse.Namespace) -> None:
    if a.reset:
        stats_mod.reset()
        print("stats cleared")
        return
    rows = [{"deployment": k, **{x: v.get(x) for x in ("ok", "fail", "latency")}, "last_error": (v.get("last_error") or "")[:60]}
            for k, v in sorted(stats_mod.load().items())]
    print(_table(rows, ["deployment", "ok", "fail", "latency", "last_error"]))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="freellm", description="Route to the best free LLMs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("keys", help="provider/key status and signup links")
    s.add_argument("--steps", action="store_true")
    s.set_defaults(fn=cmd_keys)

    sub.add_parser("init", help="create llm/.env").set_defaults(fn=cmd_init)

    s = sub.add_parser("models", help="ranked usable free models")
    s.add_argument("--tools", action="store_true")
    s.add_argument("--vision", action="store_true")
    s.add_argument("--min-context", type=int)
    s.add_argument("--pref", choices=["quality", "balanced", "speed"], default="quality")
    s.add_argument("--refresh", action="store_true", help="re-query provider model lists now")
    s.add_argument("--all", action="store_true", help="every known model, including providers without keys")
    s.add_argument("--available", action="store_true", help="only models that answered in the last `freellm ping`")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_models)

    s = sub.add_parser("ping", help="health-check the top models")
    s.add_argument("-n", type=int, default=5, help="probe the top N models (0 = all)")
    s.add_argument("--max-tokens", type=int, default=200)
    s.add_argument("--refresh", action="store_true")
    s.set_defaults(fn=cmd_ping)

    s = sub.add_parser("chat", help="one-shot prompt")
    s.add_argument("prompt", nargs="+")
    s.add_argument("-m", "--model")
    s.set_defaults(fn=cmd_chat)

    s = sub.add_parser("stats", help="recorded per-deployment health")
    s.add_argument("--reset", action="store_true")
    s.set_defaults(fn=cmd_stats)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
