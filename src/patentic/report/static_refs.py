from datetime import date
from typing import Final

from patentic.report.bundle import Reference

RETRIEVED: Final[date] = date(2026, 11, 7)

STATIC_REFERENCES: Final[list[Reference]] = [
    Reference(
        id="R-OG",
        title="USPTO Official Gazette notices: expirations for nonpayment and reinstatements",
        url="https://www.uspto.gov/learning-and-resources/official-gazette",
        retrieved=RETRIEVED,
    ),
    Reference(
        id="R-MAINT",
        title="USPTO, Maintain your patent (fee windows, grace periods, reinstatement)",
        url="https://www.uspto.gov/patents/maintain",
        retrieved=RETRIEVED,
    ),
    Reference(
        id="R-MPEP2590",
        title="MPEP 2590 and 2591: acceptance of delayed fees and intervening rights",
        url="https://www.uspto.gov/web/offices/pac/mpep/s2590.html",
        retrieved=RETRIEVED,
    ),
    Reference(
        id="R-FR",
        title="91 FR 37826 (2026): one-year threshold for unintentional-delay petitions",
        url="https://www.govinfo.gov/content/pkg/FR-2026-06-24/html/2026-12717.htm",
        retrieved=RETRIEVED,
    ),
    Reference(
        id="R-PV",
        title="Google BigQuery public dataset patents-public-data.patentsview",
        url="https://console.cloud.google.com/marketplace/product/google_patents_public_datasets/google-patents-public-data",
        retrieved=RETRIEVED,
    ),
    Reference(
        id="R-BLS",
        title="BLS Consumer Expenditure Survey 2025: housekeeping supplies, $844 per consumer unit",
        url="https://www.bls.gov/news.release/cesan.nr0.htm",
        retrieved=RETRIEVED,
    ),
]
