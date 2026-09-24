from college_agent.budget import check, four_year_cost


def test_four_year_cost_compounds():
    assert four_year_cost(40000, 4, 0.0) == 160000
    assert four_year_cost(40000, 4, 0.04) == round(40000 * (1 + 1.04 + 1.04**2 + 1.04**3))


def test_private_flags_net_price_caveat():
    r = check("P", "private_nonprofit", 90000, 45000, 200000)
    assert r["fits_budget"] is False
    assert "grant aid" in r["note"]


def test_missing_cost_is_unknown():
    assert check("X", "public", None, None, 1)["status"] == "unknown"
