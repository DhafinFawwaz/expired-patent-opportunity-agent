# Fixtures

`synthetic/` holds six made-up patents (US 9,999,901 to 9,999,906) that cover the status cases the brief asks for. None of them are real. Every evidence record carries `is_synthetic: true` and every report renders them under the heading SYNTHETIC FIXTURE.

| File | Case | Expected status | Confidence |
|---|---|---|---|
| 01-expired-nonpayment | 8-year fee unpaid, Gazette lists the lapse | expired_nonpayment | high |
| 02-reinstated | 12-year lapse, then a Gazette reinstatement | reinstated | high |
| 03-grace-period | 4-year fee unpaid, reminder mailed, anniversary still ahead | in_grace_period | medium |
| 04-end-of-term | filed in 2004, no lapse, term over | expired_end_of_term | very_low |
| 05-conflicting | OPS lapse then a later payment with no petition; one Gazette week missing | conflicting | low |
| 06-related-active | lapsed, but a continuation is still in force | expired_nonpayment | high |

Each file validates against `schemas/fixture-case.schema.json`. The `events` refer to the sources they imitate (`og_notice`, `ops`); the matching `evidence` records are labelled `fixture`.

`requests/` holds research requests and `decisions/` holds scripted answers for the two review gates.
