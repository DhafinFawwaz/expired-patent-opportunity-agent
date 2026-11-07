# Data sources

| Source | What | URL pattern | Credential | Limits | Freshness and lag | Terms | Grade | Used for | Not used for |
|---|---|---|---|---|---|---|---|---|---|
| USPTO Official Gazette notices | Weekly lists of patents expired for nonpayment and patents reinstated | `https://www.uspto.gov/web/offices/com/sol/og/<YYYY>/week<NN>/TOC.htm`, fallback `https://patentsgazette.uspto.gov/week<NN>/OG/TOC.htm` (last 52 weeks) | None | 1 request per second, every page cached forever | Archive back to 2008; expirations appear about 8 weeks after the anniversary | Public domain; the site is not meant for bulk downloads, so one cached request per week page | A | Status evidence, reinstatement scan | Titles, claims (rows carry only numbers and dates) |
| BigQuery `patents-public-data.patentsview` | Bibliographic data, CPC, claims, citations, continuity, terminal disclaimers | `patent`, `cpc_current`, `application`, `patent_assignee`, `assignee`, `claim`, `uspatentcitation`, `usreldoc`, `us_term_of_grant` | A Google Cloud project with BigQuery (sandbox works); ADC or `GOOGLE_CLOUD_ACCOUNT` | Free tier 1 TiB scanned per month; per-query cap 50 GB | Grants to 2021-09-28; `claim` to October 2019 | Google Cloud terms; data CC BY 4.0 | A for bibliographic fields, F for status | Discovery, claims, related records | Status (no maintenance data in any table) |
| EPO Open Patent Services, legal service | INPADOC legal events (lapse `LAPS`/`STCH`/`FP`, reinstatement `PRDP`) | `https://ops.epo.org/3.2/rest-services/legal/publication/docdb/US<number>` | Free registration, OAuth client credentials (`EPO_OPS_KEY`, `EPO_OPS_SECRET`) | 4 GB per week free; throttled per minute | Lapses within about two weeks; reinstatements lag months | EPO fair use charter | B | Cross-check when credentials exist | Primary status |
| USPTO ODP maintenance fee events | Every fee payment, expiry and reinstatement since 1981 | `api.uspto.gov` (key-gated) | ODP key, which needs ID.me identity verification | n/a | Weekly | USPTO terms | A | Parser shipped and tested on synthetic lines only | Live runs (no key) |

## Query costs (dry runs, 2026-11-07)

| Query | Tables | Bytes scanned |
|---|---|---|
| Discovery | `patent`, `cpc_current`, `application`, `patent_assignee`, `assignee` | 2.30 GB |
| Claims for a candidate set | `claim` | 38.95 GB |
| Forward citations | `uspatentcitation` | 2.20 GB |
| Continuity and terminal disclaimers | `usreldoc`, `us_term_of_grant` | 0.55 GB |

A fresh run scans about 44 GB. Results are cached by query text, so a same-day rerun scans nothing; the discovery window is computed from today's date and the claims query from the candidate list, so a later day costs 2.3 GB again and a new Gazette issue usually costs the 39 GB claims query again. Caching claims per patent and anchoring the window to the last Gazette Tuesday would remove most of that. Dry-run estimates can be wrong: a `TABLESAMPLE` query on `claim` estimated 77 MB but needed 39 GB, so every real query also carries a hard `maximum_bytes_billed` cap.

## What the sample run used

| Source | Live in `run-real-4` | Notes |
|---|---|---|
| Official Gazette | Yes | 104 weekly issues, 2024-11-12 to 2026-11-03, no missing weeks; about 73 MB of HTML, fetched once and cached |
| BigQuery PatentsView | Yes | 44.0 GB scanned on the first run, 0 on later runs |
| EPO OPS | No | Registration still pending; the adapter is tested against a synthetic response |
| USPTO ODP | No | Needs an ID.me-verified key; the parser is tested on sample lines |
| Google Patents (manual) | One observation | `fixtures/observations/US-8646606-google-patents.json`, recorded by hand on 2026-11-07 for the conflicting-evidence example, grade C |

Rejected sources: Patent Public Search (no API), Lens.org (approval-gated, unclear terms for this use), IFI CLAIMS (enterprise pricing), and any shared or bought USPTO key (one key per verified person under USPTO terms).
