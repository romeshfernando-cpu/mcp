from college_agent.fit import SchoolEvidence, classify


def test_very_selective_is_always_reach():
    r = classify(SchoolEvidence("X", overall_admit_rate=0.09), 4.4, True)
    assert r.label == "reach"


def test_test_blind_ignores_act():
    ev = SchoolEvidence("UC", overall_admit_rate=0.5, test_policy="test_blind", act_25=30, act_75=35)
    r = classify(ev, 4.0, True, act_composite=20)
    assert any("ignored" in s for s in r.reasons)
    assert r.label == "target"


def test_low_act_hurts_where_tests_count():
    ev = SchoolEvidence("P", overall_admit_rate=0.5, test_policy="test_optional", act_25=30, act_75=35)
    r = classify(ev, None, True, act_composite=24)
    assert any("below the 25th" in s for s in r.reasons)


def test_source_school_data_preferred_and_high_confidence():
    ev = SchoolEvidence("UCSB", overall_admit_rate=0.33, source_applicants=100,
                        source_admits=40, source_admit_mean_gpa=4.30)
    r = classify(ev, 4.05, True)
    assert r.rate_source.startswith("student's high school")
    assert r.label == "reach"  # 40% rate is moderate, GPA 0.25 below admits -> reach
    assert r.confidence == "high"


def test_suppressed_source_data_falls_back():
    ev = SchoolEvidence("Merced", overall_admit_rate=0.89, source_applicants=4, source_admits=3)
    r = classify(ev, 4.0, True)
    assert r.rate_source == "overall admit rate"


def test_safety_requires_high_rate_and_gpa_margin():
    ev = SchoolEvidence("R", overall_admit_rate=0.7, source_applicants=50,
                        source_admits=40, source_admit_mean_gpa=4.05)
    assert classify(ev, 4.2, True).label == "safety"
    assert classify(ev, 4.0, True).label == "target"


def test_unverified_gpa_lowers_confidence_and_warns():
    ev = SchoolEvidence("R", overall_admit_rate=0.7, source_applicants=50,
                        source_admits=40, source_admit_mean_gpa=4.05)
    r = classify(ev, 4.2, False)
    assert r.confidence != "high"
    assert any("UC-calculated" in w for w in r.warnings)


def test_no_data_is_unknown_not_guessed():
    assert classify(SchoolEvidence("?"), 4.0, True).label == "unknown"
