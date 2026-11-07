# Limitations

These are the limits a reader of the report should know about, and what would remove each one.

## Data coverage

- **US only.** Every source and rule is for US utility patents. Nothing in the output says anything about other countries.
- **PatentsView ends with grants of 2021-09-28.** The BigQuery `patentsview` tables stop there, and the `claim` table stops in October 2019. Patents lapsing at the 8- and 12-year stages in the current window are fully covered; lapses at the 4-year stage are only partly covered, because the newest grants are missing. `patents-public-data.patents.publications` has grants to 2026-09-15 and would close the gap, at about 37 GB for discovery and 128 GB for claims per fresh run. It is documented in `docs/data-sources.md` and not built.
- **The Gazette scan covers 104 weeks** (2024-11-12 to 2026-11-03 in the sample run). A patent that lapsed earlier is not found, and a reinstatement published after the last issue read is not seen. Expirations appear in the Gazette about 8 weeks after the anniversary (the sample shows 2026-09-04 expiries in the 2026-11-03 issue), so the most recent lapses are not listed yet.
- **Gazette rows have no titles or owners**, only numbers and dates. Titles, CPC codes and claims come from PatentsView, so a patent outside PatentsView's range cannot be described even if the Gazette lists it.

## Status

- **No live maintenance fee history.** The USPTO's own fee event data needs an ODP key, which needs ID.me identity verification. The parser is built and tested on sample lines but was not used live. Status therefore rests on the Gazette notices alone.
- **EPO OPS lags on reinstatements.** INPADOC records lapses within about two weeks but can take months to record a reinstatement, so a later official Gazette notice always overrides it. Without EPO credentials a run falls back to the Gazette alone, which caps confidence at `high`.
- **Petitions are not visible.** A petition to accept a late payment can be pending without any Gazette notice. The report says to check Patent Center before relying on an expiry.
- **Patent term adjustment is unknown.** Term end is estimated as 20 years from the earliest US non-provisional filing, and the report says the adjustment is not known.
- **Terminal disclaimers** are checked only where PatentsView records them.
- **Related patents are listed, not verified.** Each related record (continuation, citation, same assignee, reissue) carries a "to verify" flag. A related patent that is still in force can block a product even when the candidate has expired.

## Screening and scoring

- **The power screen is rule-based first.** Tier 1 drops powered CPC co-classes; tier 2 drops independent claims that recite a motor, battery, heater and similar terms (hand pumps and trigger sprayers excepted). Tier 3 asks the model, and its answer can be `unclear`, which is flagged rather than dropped.
- **Free models vary from run to run.** Claim summaries, opportunity rationales and the commercial and effort scores come from free models through `freellm`. Live runs on the same data shortlisted different second candidates (US 10,052,751, US 10,052,665 and US 8,826,487 across three runs). Status, confidence and evidence quality do not depend on the model. `--replay` reruns the committed sample with its recorded answers, so the sample itself is reproducible.
- **Model calls can fall back.** When a free model returns empty or invalid output twice, the step uses its template instead. The sample run had 5 fallbacks out of 20 calls; the cost record and event log list them.
- **Only the top 8 eligible candidates are analysed.** The rest are counted as "eligible but not analysed" in the report, not silently dropped.
- **Commercial relevance is a model judgement on the claims.** No market data is used; the Census shipment lookup in the design was cut.

## Output

- **Page count is checked only with `--render`.** The check renders the report to PDF with LibreOffice. It is opt-in because LibreOffice is slow and macOS asks the user to approve it on first launch. CI runs it as a non-blocking job.
- **This is screening, not clearance.** Every file carries the label "Research screening only. Not a legal opinion or freedom-to-operate determination." Design patents, trade dress and related patents can still cover a product.
