# Time and cost

Hours are wall-clock, taken from commit times in UTC+7. They measure elapsed time between commits, so short gaps mean the work happened quickly, not that it was skipped. Research and design (2026-11-07, before the build) are listed separately and are not part of the 10-hour build target.

| Phase | Task | Started | Ended | Hours | Notes |
|---|---|---|---|---|---|
| Build | 1 Workspace, tooling, CI | 16:00 | 16:26 | 0.45 | freellm copied in; LiteLLM needed `LITELLM_LOCAL_MODEL_COST_MAP` for offline tests |
| Build | 2 Type freellm strictly | 16:26 | 16:29 | 0.05 | baseline was 215 ruff findings and 26 mypy errors in llm/ |
| Build | 3 Spec, ADRs, docs skeleton | 16:29 | 16:30 | 0.02 | |
| Build | 4 Identifiers | 16:30 | 16:31 | 0.02 | |
| Build | 5 Event vocabulary | 16:31 | 16:32 | 0.02 | |
| Build | 6 Status rules | 16:32 | 16:35 | 0.05 | fixed a month-arithmetic bug found by the tests |
| Build | 7 Confidence and grades | 16:35 | 16:36 | 0.02 | replaced an 8-week lag rule that real Gazette data contradicted |
| Build | 8 Evidence records and fixtures | 16:36 | 16:38 | 0.03 | |
| Build | 9 Screening, term, related, scoring | 16:38 | 16:40 | 0.03 | |
| Build | 10 HTTP source | 16:40 | 16:42 | 0.03 | |
| Build | 11 Gazette parser | 16:42 | 16:44 | 0.03 | two real pages trimmed into test data |
| Build | 12 BigQuery gateway | 16:44 | 16:49 | 0.08 | one live discovery query, about 2.3 GB |
| Build | 13 EPO OPS adapter | 16:49 | 16:51 | 0.03 | built against a synthetic response; credentials pending |
| Build | 14 Maintenance fee file parser | 16:51 | 16:52 | 0.02 | |

## Run cost

Filled in after the real run: BigQuery bytes scanned, LLM cost, wall time.
