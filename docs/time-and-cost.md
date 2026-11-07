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
| Build | 15 LLM calls and fallbacks | 16:52 | 16:56 | 0.07 | |
| Build | 16 State, plan, approval gate | 16:56 | 16:58 | 0.03 | |
| Build | 17 Discovery and status fan-out | 16:58 | 17:01 | 0.05 | |
| Build | 18 Analysis, scoring, review gate | 17:01 | 17:03 | 0.03 | |
| Build | 19 CLI, run log, resume | 17:03 | 17:12 | 0.15 | a first version hung retrying 104 failing weeks; added an offline mode and a circuit breaker |
| Build | Checkpoint after task 19 | | 17:12 | 1.2 total | under the 7.5 h cut line, nothing cut |
| Build | 20 Report bundle | 17:12 | 17:16 | 0.07 | |
| Build | 21 Word report | 17:16 | 17:18 | 0.03 | |
| Build | 22 Deck | 17:18 | 17:21 | 0.05 | |
| Build | 23 Cross-file validation | 17:21 | 17:27 | 0.10 | LibreOffice render made opt-in after a macOS Gatekeeper prompt |
| Build | 24 First real run and fixes | 17:27 | 19:32 | 2.08 | four live runs; run 1 exposed a relative-path bug in the OOXML check and a 1024-token cap that truncated model answers; most of the time was free-model latency |

## Run cost

Sample run `run-real-4` (committed under `outputs/samples/` and `docs/sample-logs/`):

| Item | Value |
|---|---|
| BigQuery bytes, first fresh run | 44.0 GB (discovery 2.30, claims 38.95, citations 2.20, continuity 0.55), inside the 1 TB monthly free tier |
| BigQuery bytes, later runs | 0, every query was served from the local cache |
| Gazette pages fetched | 104 weekly issues, about 73 MB of HTML, fetched once at one request per second |
| LLM calls | 20 (4 fell back to templates), 28k tokens in, 72k out |
| LLM cost | $0.00 on free models through `freellm` |
| Wall time | about 15 minutes, almost all of it model latency on free tiers |

The replay bundle (`fixtures/replay/`, 10 MB) reruns this result offline in about 6 seconds.
