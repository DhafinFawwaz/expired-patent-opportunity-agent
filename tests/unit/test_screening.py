from patentic.domain.screening import (
    CpcSets,
    PowerTerms,
    is_core_hit,
    load_cpc_sets,
    load_power_terms,
    tier1_rejects,
    tier2_power_hits,
)

SETS: CpcSets = load_cpc_sets()
TERMS: PowerTerms = load_power_terms()


def test_core_hit_a47l13() -> None:
    assert is_core_hit(["A47L13/20"], SETS)
    assert is_core_hit(["A47K11/10"], SETS)
    assert not is_core_hit(["A47J43/28"], SETS)


def test_supporting_needs_household_index() -> None:
    assert not is_core_hit(["A46B9/04"], SETS)
    assert is_core_hit(["A46B9/04", "A46B2200/3033"], SETS)


def test_tier1_rejects_suction_cleaner() -> None:
    assert "A47L9/" in tier1_rejects(["A47L13/20", "A47L9/2805"], SETS)


def test_tier1_keeps_carpet_sweeper_exception() -> None:
    assert tier1_rejects(["A47L11/33"], SETS) == []
    assert tier1_rejects(["A47L11/4011"], SETS) == ["A47L11/"]


def test_tier2_motor_in_independent_claim() -> None:
    hits: list[str] = tier2_power_hits(["A mop comprising a motor driving a pad."], TERMS)
    assert hits == ["motor"]


def test_tier2_hand_pump_allowed() -> None:
    claims: list[str] = ["A spray mop with a hand-operated pump and a trigger sprayer."]
    assert tier2_power_hits(claims, TERMS) == []


def test_tier2_bare_pump_rejected() -> None:
    assert tier2_power_hits(["A mop with a pump feeding the pad."], TERMS) == ["pump"]


def test_tier2_led_is_case_sensitive() -> None:
    assert tier2_power_hits(["A handle that led the user to the pad."], TERMS) == []
    assert tier2_power_hits(["A handle with an LED indicator."], TERMS) == ["LED"]


def test_tier2_term_only_in_dependent_claim_not_rejected() -> None:
    assert tier2_power_hits(["A brush comprising bristles on a head."], TERMS) == []
