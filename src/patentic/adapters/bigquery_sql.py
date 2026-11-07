from typing import Final

PV: Final[str] = "`patents-public-data.patentsview"

DISCOVERY_SQL: Final[str] = f"""
WITH hits AS (
  SELECT DISTINCT c.patent_id
  FROM {PV}.cpc_current` c
  WHERE EXISTS (SELECT 1 FROM UNNEST(@prefixes) pre WHERE STARTS_WITH(c.subgroup_id, pre))
),
base AS (
  SELECT p.id, p.kind, p.date, p.title, p.num_claims
  FROM {PV}.patent` p
  JOIN hits h ON h.patent_id = p.id
  WHERE p.type = 'utility' AND p.kind IN ('B1', 'B2')
    AND p.date BETWEEN @grant_from AND @grant_to
),
codes AS (
  SELECT c.patent_id, ARRAY_AGG(DISTINCT c.subgroup_id ORDER BY c.subgroup_id) AS cpc
  FROM {PV}.cpc_current` c JOIN base b ON b.id = c.patent_id
  WHERE c.subgroup_id IS NOT NULL
  GROUP BY c.patent_id
),
filed AS (
  SELECT a.patent_id, MIN(a.date) AS filing_date
  FROM {PV}.application` a JOIN base b ON b.id = a.patent_id
  GROUP BY a.patent_id
),
owners AS (
  SELECT pa.patent_id,
    ARRAY_AGG(DISTINCT COALESCE(s.organization, CONCAT(s.name_first, ' ', s.name_last))
      IGNORE NULLS) AS assignees
  FROM {PV}.patent_assignee` pa
  JOIN base b ON b.id = pa.patent_id
  JOIN {PV}.assignee` s ON s.id = pa.assignee_id
  GROUP BY pa.patent_id
)
SELECT b.*, codes.cpc, filed.filing_date, owners.assignees
FROM base b
LEFT JOIN codes ON codes.patent_id = b.id
LEFT JOIN filed ON filed.patent_id = b.id
LEFT JOIN owners ON owners.patent_id = b.id
ORDER BY b.id
"""

CLAIMS_SQL: Final[str] = f"""
SELECT patent_id, sequence, dependent, text
FROM {PV}.claim`
WHERE patent_id IN UNNEST(@ids)
"""

CITATIONS_SQL: Final[str] = f"""
SELECT citation_id, patent_id
FROM {PV}.uspatentcitation`
WHERE citation_id IN UNNEST(@ids)
ORDER BY citation_id, patent_id
"""

CONTINUITY_SQL: Final[str] = f"""
SELECT r.patent_id, r.doctype, r.relkind, r.reldocno, t.term_disclaimer
FROM {PV}.usreldoc` r
LEFT JOIN {PV}.us_term_of_grant` t ON t.patent_id = r.patent_id
WHERE r.patent_id IN UNNEST(@ids)
  AND r.doctype IN ('continuation', 'continuation-in-part', 'division', 'reissue')
UNION ALL
SELECT t.patent_id, NULL, NULL, NULL, t.term_disclaimer
FROM {PV}.us_term_of_grant` t
WHERE t.patent_id IN UNNEST(@ids)
"""
