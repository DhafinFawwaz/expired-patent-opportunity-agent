# Demo plan

A 20-minute demo, step by step: 5 minutes of architecture, 10 of live runs, 5 of tests and failures. It covers the three cases the brief asks for: a reinstated fixture, a conflicting status and a source outage. Run every command from the repository root.

Each step says what to type, what you will see, and what to point at.

## Before the day

1. Pull and install:

   ```bash
   git pull
   make install
   ```

2. Check that `.env` has `GOOGLE_CLOUD_PROJECT` (and the EPO keys if you have them), and that `gcloud auth application-default login` is still valid. The outage run in step 7 needs BigQuery or its cache.

3. Warm the caches, so nothing waits on a free model during the talk:

   ```bash
   make demo-auto
   make replay
   uv run patentic run --simulate-outage og --decisions fixtures/decisions/approve-all.yaml --no-llm
   make check
   ```

   The first `make demo-auto` on a machine can take about 8 minutes because of the free-model calls. After that `make demo` takes about 11 seconds. If it is still slow on the day, add `--no-llm` (step 4) and say why.

4. Open these in a browser tab or editor before you start:
   - the README on GitHub (for the mermaid diagram)
   - `docs/architecture.md`
   - `docs/adr/002-workflow-not-agent.md`, `004`, `005`

5. Make the terminal font large and clear the screen.

## Part 1: Architecture (0:00 to 5:00)

**Step 1. The problem (30 s).** Say what the agent does: find US patents that look expired for unpaid maintenance fees, check the dated evidence including any reinstatement, and write a matching Word report and PowerPoint deck. Say it is research screening, not legal clearance.

**Step 2. The graph (2 min).** Show the mermaid diagram in the README. Walk it top to bottom:
- intake and plan, then the probe rounds against BigQuery, then gate 1
- discovery on the approved CPC codes, the Gazette status index, claims, the non-powered screen
- status verification per candidate, rank, analyse, score, gate 2
- bundle, generate, validate, with up to three retries if the files do not match

Point out that it is a fixed LangGraph workflow, not an autonomous agent (ADR 002).

**Step 3. Where the model is used (1 min).** Plan and its refinement, claim summaries, opportunity rationale, report prose. Each call has a schema, a check and a template fallback. Status, confidence and scores come from code (ADR 004).

**Step 4. Evidence and outputs (1.5 min).** Status comes from the USPTO Official Gazette lists, keyless and dated, with EPO legal events as a second source. One validated bundle renders the report and the deck, and the validator compares every file with it afterwards (ADR 005).

## Part 2: Live demo (5:00 to 15:00)

### Run 1: synthetic fixtures (5:00 to 9:00)

**Step 5. Start the demo.**

```bash
make demo
```

Say: six made-up patents, US 9,999,901 to 9,999,906, offline, no keys. They are labelled SYNTHETIC FIXTURE in every output.

**Step 6. Gate 1.** A plan table appears, then:

```
Plan [approve/revise/abort] (approve):
```

Point at the CPC codes and the line that says what the search adds to the default set. Say the approved codes are what discovery searches. Type:

```
approve
```

**Step 7. Watch the status lines.** As it runs, the terminal prints one line per patent. Point at these two:

```
status assessed key=US-9999902, label=reinstated, confidence=high
status assessed key=US-9999905, label=conflicting, confidence=low
```

- US 9,999,902 was listed as expired, then reinstated. The later official notice wins, so it is not a candidate.
- US 9,999,905 has two sources that disagree, so the label is conflicting with low confidence, and it is not reported as an opportunity until someone checks it by hand.

Also mention the others in one breath: 9,999,903 in its grace period, 9,999,904 past its 20-year term, 9,999,901 and 9,999,906 cleanly expired for nonpayment.

**Step 8. Gate 2.** A candidate table appears with US 9,999,901 and US 9,999,906, then:

```
Candidates [accept/edit/abort] (accept):
```

Say only the clean expiries reach this gate. Type:

```
accept
```

Wait for `validation checked ok=True` and `Run completed`.

**Step 9. Open the report.**

```bash
open outputs/runs/$(ls -t outputs/runs | head -1)/report.html
```

Scroll to section 4, "Patent-status evidence timelines". Point at the worked example for US 9,999,902: the 2026-08-04 expiry notice, the 2026-09-29 reinstatement, and the note about intervening rights for anyone who started using it during the lapse. Every row has a date and a source.

### Run 2: the real result (9:00 to 12:00)

**Step 10. Replay the real run.**

```bash
uv run patentic run --replay
```

Type `approve` at gate 1 and `accept` at gate 2. It finishes in about 10 seconds.

While it runs, say: the live run took about 73 minutes, almost all free-model latency. It looked at 2,404 cleaning-tool patents, found 299 listed as expired in 104 weeks of Gazette notices, and shortlisted two. Replay reruns it from recorded data with no keys.

**Step 11. Open the deck.**

```bash
open outputs/runs/$(ls -t outputs/runs | head -1)/deck.html
```

Step through with the arrow keys:
- "Candidate comparison": US 8,800,092 (flat mop with a trigger that releases the cloth) and US 8,826,487 (mop set with a built-in wringer), both expired for nonpayment at very high confidence because the Gazette and EPO agree.
- "Status-verification example": US 8,646,606, the real conflicting case. The Gazette listed it as reinstated on 2026-10-07, while Google Patents still showed it as expired. patentic follows the later official notice and keeps the other observation visible.
- "Commercial assessment": the model rates commercial relevance and engineering effort; code computes evidence quality, risk and the weighted total.

### Run 3: a source outage (12:00 to 15:00)

**Step 12. Make the Gazette fail.**

```bash
uv run patentic run --simulate-outage og --decisions fixtures/decisions/approve-all.yaml --no-llm
```

Say the decisions file answers both gates, so there is nothing to type. It finishes in a few seconds.

**Step 13. Show what it recorded.**

```bash
grep outage outputs/runs/$(ls -t outputs/runs | head -1)/events.jsonl
open outputs/runs/$(ls -t outputs/runs | head -1)/report.html
```

- The log has one outage event for the Gazette, not 104 retries.
- The executive summary says the Official Gazette could not be reached, so no candidate is reported.
- The files were still written and passed validation.

Say the rule: when the evidence is missing, the run says so instead of guessing. `--simulate-outage bigquery` does the same for discovery.

**Optional, if you are ahead of time: stop and resume.**

```bash
uv run patentic demo --no-llm --decisions fixtures/decisions/stop-at-review.yaml
```

It stops at gate 2 and prints `Resume with: patentic resume <run id>`. Copy that command, run it, and type `accept`. The state was saved in SQLite after every step.

## Part 3: Tests and failures (15:00 to 20:00)

**Step 14. Run the checks.**

```bash
make check
```

It runs ruff, mypy strict and 332 tests in about 30 seconds, all offline with sockets blocked. GitHub Actions runs the same on every push.

**Step 15. Show a few tests while it runs.**
- `tests/unit/test_status_rules.py`: the status rules, including a reinstatement granted before the expiry notice was printed.
- `tests/report/test_validate.py`: a deliberately mismatched file fails validation.
- `tests/e2e/test_replay.py`: the real run reproduced offline.
- `tests/graph/test_plan_scope.py`: plan codes reach discovery and bad codes are refused.

**Step 16. Real failures from the build (1.5 min).**
- A run hung retrying 104 failing Gazette weeks. Fixed with an offline mode and a circuit breaker.
- A 1024-token output cap cut model answers short, so they kept falling back to templates.
- The simulated outage showed nothing because cached Gazette pages hid it. The outage mode now uses an empty cache.
- Reinstatements granted before the expiry notice was printed were missed. Found in review, fixed with a test.
- The plan approved at gate 1 was not used by discovery. Now the approved codes drive the search.

**Step 17. Limitations (1 min).** Open `docs/limitations.md` and name the main ones:
- PatentsView ends with grants of 2021-09-28, so 4-year lapses are only partly covered.
- The Gazette scan covers 104 weeks and lags about 8 weeks behind expiry.
- No live fee history without an ODP key, so pending petitions are invisible.
- Related patents are listed and flagged, not checked for claim overlap.
- Free models vary between runs. Status, confidence and evidence never depend on the model.

**Step 18. Close (30 s).** Fixed workflow, dated public evidence with a second source, rules for status and confidence, the model only where it helps, one dataset behind every file. Research screening only, not a legal opinion or freedom-to-operate determination.

## If something goes wrong

| Problem | What to do |
|---|---|
| `make demo` hangs on a model call | Ctrl+C, then `uv run patentic demo --no-llm` and say the model steps now use templates |
| Network is down | Runs 1 and 2 are offline already. For run 3 add `--offline` so it reads the BigQuery cache from the warm-up |
| A gate prompt was answered wrong | Type `abort` and start the step again |
| The wrong run opens | List runs with `ls -t outputs/runs` and open the folder by name |
