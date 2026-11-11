# Using patentic

This guide covers setup, the request file, the two questions a run asks you, and where the results go. Every command here runs from the repository root.

## 1. Setup

You need Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
```

That is enough for the demo and the replay. A live run also needs BigQuery:

1. Create a Google Cloud project (the free BigQuery sandbox is enough) and put its id in `.env` as `GOOGLE_CLOUD_PROJECT`.
2. Log in once: `gcloud auth application-default login`.
3. Optional: add `EPO_OPS_KEY` and `EPO_OPS_SECRET` to `.env` for the second status source. Without them status rests on the Gazette alone.
4. Optional: add free model keys to `llm/.env` to make the model steps faster. `make llm-keys` lists where to get them. With no keys the run still works through the keyless providers, just slowly.

## 2. Pick a mode

| You want to | Command | Needs |
|---|---|---|
| See the whole pipeline on made-up patents | `make demo` | nothing |
| Rerun the committed real result | `make replay` | nothing |
| Search real patents | `make run` | BigQuery |
| Search real patents with no prompts | `make run-auto` | BigQuery |
| Show what happens when a source is down | `make outage OUTAGE=og` | BigQuery |

`make help` lists every target. Each one is a short wrapper around `uv run patentic ...`, so you can call the CLI directly with the flags in section 6.

## 3. The request file

`--request-file` takes a YAML file that describes what you are looking for. The run reads it at the start and the model drafts its search plan from it. If you leave the flag out, `patentic run` uses `fixtures/requests/demo-cleaning-tools.yaml`, the request from the case study:

```yaml
technology_category: non-powered household cleaning tools
intended_product: >-
  Manual cleaning tools for home use (mops, brushes, squeegees, scrapers, dust pans)
  that a small manufacturer could make without electronics.
commercial_constraints:
  - US market only; do not infer worldwide availability
  - recommend at most two candidates for technical and legal review
  - return fewer than five if the evidence does not support five
max_candidates: 5
max_recommended: 2
lapse_window_weeks: 104
```

| Field | Required | Meaning |
|---|---|---|
| `technology_category` | yes | Short name of the field you are searching |
| `intended_product` | yes | What you would make. The model uses it to judge fit and write the rationale |
| `commercial_constraints` | no | Free-text rules the plan and the report should respect |
| `max_candidates` | no, default 5 | How many candidates go into the report (1 to 10) |
| `max_recommended` | no, default 2 | How many can be recommended for review (0 to 2) |
| `lapse_window_weeks` | no, default 104 | How far back to look for expiry notices, in weeks (1 to 520) |
| `jurisdiction` | no | Always `US`; any other value is rejected |

The full schema is `schemas/research-request.schema.json`.

To write your own, copy the demo file and edit it:

```bash
cp fixtures/requests/demo-cleaning-tools.yaml my-request.yaml
# edit my-request.yaml
uv run patentic run --request-file my-request.yaml
# or
make run REQUEST=my-request.yaml
```

One limit to know before you write a request for a different field: the CPC sets and the powered-tool screen in `src/patentic/config/cpc_sets.yaml` are built for non-powered household cleaning tools. The model can add codes to the search, but only inside the subclasses that file already covers, and it ignores the rest (the plan gate shows which codes it ignored and why). A request for, say, kitchen gadgets that are not cleaning tools will find little until that file is extended.

## 4. Answering the two gates

An interactive run stops twice and waits for you to type an answer in the terminal.

**Gate 1, the plan.** You see the plan as a table: CPC codes, search terms, exclusions and sources. Below it are the codes the search adds to the default set, any codes the run ignored, and how many patents each probe round found. Then:

```
Plan [approve/revise/abort] (approve):
```

- `approve` (or just Enter) starts the search with this plan.
- `revise` asks "What should change". Type plain text, for example `drop window squeegees, add toilet brushes`. The model redrafts the plan and you see the gate again. You can revise up to three times.
- `abort` ends the run.

**Gate 2, the candidates.** This comes after status checks and scoring. You see a table with patent number, title, status, confidence, score, recommendation and flags. Then:

```
Candidates [accept/edit/abort] (accept):
```

- `accept` writes the report with the candidates as they are.
- `edit` asks three more questions. Use the patent keys from the table, such as `US-8800092`, comma separated:
  - `Drop`: candidates to remove from the report.
  - `Shortlist`: up to two to recommend for technical and legal review.
  - `Flag a candidate`: one key, then a note that goes into the report next to it.
- `abort` ends the run without writing files.

## 5. Running without prompts

`--decisions` takes a YAML list of answers, used in order, one per gate:

```yaml
- action: approve
- action: accept
```

That is `fixtures/decisions/approve-all.yaml`, and `make run-auto`, `make demo-auto` and `make replay` use it. A file can also revise, edit or stop:

```yaml
- action: revise
  feedback: drop window squeegees
- action: approve
- action: edit
  drop: [US-8826487]
  shortlist: [US-8800092]
  flag:
    US-8800092: check the trigger mechanism against current products
```

A `- stop: true` entry stops the run at that gate. `fixtures/decisions/stop-at-review.yaml` does this at gate 2, which is how you test resuming.

## 6. Commands and flags

```bash
uv run patentic run [flags]      # live run
uv run patentic demo [flags]     # six synthetic patents, offline
uv run patentic resume <run id>  # continue a stopped run
uv run patentic cost <run id>    # BigQuery bytes, model calls, tokens, cost
uv run patentic schemas          # rewrite the JSON Schemas in schemas/
```

Flags for `run`:

| Flag | Effect |
|---|---|
| `--request-file FILE` | The request YAML (section 3) |
| `--decisions FILE` | Answer the gates from a file (section 5) |
| `--replay` | Rerun the committed real run from `fixtures/replay/`, offline |
| `--offline` | Use cached data only; anything not cached is treated as unavailable |
| `--no-llm` | Skip the model; every model step uses its template |
| `--simulate-outage og\|bigquery\|ops` | Make one source fail |
| `--og-weeks N` | Gazette weeks to scan (default 104) |
| `--render` | Also render the report to PDF with LibreOffice and count pages |
| `--thread-id ID` | Choose the run id instead of a generated one |

`demo` takes `--decisions`, `--no-llm`, `--render` and `--thread-id`. `resume` takes `--decisions`.

## 7. Stopping and resuming

The run saves its state after every step. If you press Ctrl+C, close the terminal, or a source times out, continue where it left off:

```bash
uv run patentic resume <run id>
make resume            # the newest run
make resume ID=<run id>
```

The run id is printed at the start and is the folder name under `outputs/runs/`.

## 8. Results

Each run writes to `outputs/runs/<run id>/`. `make latest` prints the newest folder and its files.

| File | What it is |
|---|---|
| `report.docx`, `report.html` | The report, as Word and as a web page |
| `deck.pptx`, `deck.html` | The slide deck, as PowerPoint and as a web page (arrow keys to step) |
| `bundle.json` | The data all four files are rendered from |
| `validation.json` | Checks that each file matches the bundle |
| `events.jsonl` | The event log, with keys redacted |
| `cost.json` | BigQuery bytes, model calls and cost (`patentic cost <run id>` prints it) |
| `run.json`, `checkpoints.sqlite` | Run settings and the saved state used by `resume` |

Synthetic patents from the demo are numbered US 9,999,901 to 9,999,906 and marked SYNTHETIC FIXTURE everywhere they appear.

## 9. Cost and cache

The first live run scans about 44 GB of BigQuery data, well inside the 1 TB monthly free tier. Later runs reuse `.cache/`: discovery is kept for the calendar year, claims and citations per patent, Gazette pages forever, EPO answers for a week, and model answers by prompt. `make clean-cache` deletes the cache so the next run fetches everything again.

## 10. Common problems

| Symptom | Cause and fix |
|---|---|
| BigQuery permission or project error | `GOOGLE_CLOUD_PROJECT` is missing from `.env`, or you have not run `gcloud auth application-default login` |
| Model steps are very slow | No keys in `llm/.env`, so calls go to the keyless providers. Add a key (`make llm-keys`) or use `--no-llm` |
| No EPO cross-check in the report | `EPO_OPS_KEY` and `EPO_OPS_SECRET` are not set, so status rests on the Gazette alone |
| `--offline` run finds nothing | The data it needs is not cached yet, so it counts as unavailable. Run once online first |
| Plan gate says a code was ignored | The code is outside the subclasses in `cpc_sets.yaml` (see the limit in section 3) |

The output is research screening only. It is not a legal opinion or a freedom-to-operate determination.
