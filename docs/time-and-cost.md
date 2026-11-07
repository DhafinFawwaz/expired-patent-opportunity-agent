# Time and cost

Hours are wall-clock, taken from commit times. Research and design (2026-11-07, before the build) are listed separately and are not part of the 10-hour build target.

| Phase | Task | Started | Ended | Hours | Notes |
|---|---|---|---|---|---|
| Build | 1 Workspace, tooling, CI | 16:00 | 16:26 | 0.45 | freellm copied in; LiteLLM needed `LITELLM_LOCAL_MODEL_COST_MAP` for offline tests |
| Build | 2 Type freellm strictly | 16:26 | 16:29 | 0.05 | baseline was 215 ruff findings and 26 mypy errors in llm/ |

## Run cost

Filled in after the real run: BigQuery bytes scanned, LLM cost, wall time.
