# ADR-001: freellm design

- Status: accepted, 2026-11-07
- Context: The agent we're building (LangChain/LangGraph plus an interactive terminal) needs LLM calls that cost nothing. Free tiers are small, rate-limited and change monthly. One model is often offered by several aggregators and by its official API at once, and we may hold several keys.

## Decision

1. **Library, not proxy.** freellm is a Python package in `llm/` (`freellm`), imported directly with `from freellm import get_chat_model`. That avoids running a LiteLLM proxy server.
2. **LiteLLM Router as the engine.** Each deployment is one (provider, model id, key). Ranked models map to `order` levels 1..N in the `free*` groups. Deployments of the same model share a level, so load spreads over keys and providers. The router handles retries, cooldowns and fallback.
3. **Every provider goes through its OpenAI-compatible endpoint** (`openai/<id>` + `api_base`). This gives one code path, and `/models` discovery works the same everywhere. A per-provider `litellm_prefix` override exists if a native adapter is ever needed.
4. **Live discovery instead of a hand-maintained model list.** freellm reads `/models` for each usable provider (12 h cache) and applies a `free_filter` rule per provider. Seed lists are a fallback only.
5. **Rank by LMArena Elo** (keyless HF dataset, 24 h cache), adjusted by local stats:
   - success rate: up to −200;
   - rate-limited in the last 10 minutes: −150;
   - auth failure: −1000;
   - latency, only for the `balanced` and `speed` preferences.

   Stats persist in `.cache/stats.json`, so the ranking learns across runs.
6. **Keys in `llm/.env`** (git-ignored; `.env.example` is committed). Variables follow `<KEY_ENV>`, `<KEY_ENV>_2`, … or comma-separated values. Real environment variables override the file.
7. **Zero-effort start.** Keyless OVH and LLM7 are always included, so the library works before any signup.
8. **LangChain surface = `ChatLiteLLMRouter`**, with groups `free`, `free-tools`, `free-vision` and `free-fast`, plus one group per model and per exact deployment.

## Rejected
- **Depending on freellmpool or freellmapi.** One is httpx-only with no LangChain integration; the other is a Node server with a premium catalog.
- **Scraping freellm.net.** It's an HTML directory with no API, and its ids are sometimes slugs rather than real API ids.
- **LangChain `with_fallbacks`.** It returns a Runnable, which loses `bind_tools` and `with_structured_output` on the result. It also can't spread load over keys.
- **Hand-curated quality scores.** They go stale within weeks, and the leaderboard is free and current.
- **Artificial Analysis.** It needs a key, and the v2 data endpoints are gone.

## Consequences
- Keyed providers are configured from their docs and are only confirmed once keys are added; `freellm ping` exposes broken ones.
- Tool-calling capability is known only where a provider reports it. Elsewhere it's assumed, and the fallback chain hides failures that raise errors, but not a model that silently ignores tools.
- Anonymous providers need an httpx hook on `litellm.client_session`. That changes LiteLLM's shared sessions for the whole process; the hook only strips freellm's own sentinel header, so other requests are unaffected.

## Later improvements
- Use the keyless OpenRouter `/endpoints` uptime data as a health prior.
- Count per-key RPD/TPD from response headers, as freellmapi does.
- Add LMArena `webdev` and `agent` categories for task-specific ranking.
- Detect degenerate output (for example, the same line repeated until max_tokens) and treat it as a failure.
