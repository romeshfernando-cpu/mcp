import json

import pytest


def payload(result):
    assert not result.is_error, result
    return result.structured_content or json.loads(result.content[0].text)


@pytest.mark.anyio
async def test_end_to_end_demo_flow(server):
    p = payload(await server.call_tool("save_student_profile", {
        "high_school": "Example High School", "weighted_gpa": 4.2, "act_composite": 26,
        "intended_majors": ["environmental science", "sports psychology"],
        "major_flexible": True, "savings": 200000, "prefers_public": True}))
    pid = p["profile_id"]
    assert any("uc_gpa" in g for g in p["missing_for_best_results"])

    s = payload(await server.call_tool("search_colleges", {"ownership": "public"}))
    assert all(x["ownership"] == "public" for x in s["schools"])
    ucsb = next(x for x in s["schools"] if x["unitid"] == 110705)
    assert ucsb["test_policy"] == "test_blind" and ucsb["major_affects_admission"] is False

    f = payload(await server.call_tool("classify_fit", {
        "profile_id": pid, "unitids": [110705, 110671, 445188, 110422],
        "intended_discipline": "Agriculture"}))
    by = {r["unitid"]: r for r in f["results"]}
    assert f["gpa_verified"] is False
    assert by[110705]["rate_source"].startswith("student's high school")
    assert by[445188]["rate_source"] == "overall admit rate"  # suppressed source data
    assert by[110422]["rate_source"].startswith("admit rate for the intended college")
    assert all("ignored" in " ".join(r["reasons"]) for r in f["results"])  # all test-blind

    b = payload(await server.call_tool("check_budget", {"profile_id": pid, "unitids": [110705, 999001]}))
    fits = {r["unitid"]: r["fits_budget"] for r in b["results"]}
    assert fits == {110705: True, 999001: False}

    d = payload(await server.call_tool("get_deadlines", {"unitids": [110705, 110422, 999001]}))
    by = {r["unitid"]: r for r in d["results"]}
    assert by[110705]["deadline"] == "2026-11-30" and by[110705]["early_action_available"] is False
    assert by[110422]["early_action_available"] is False
    assert by[999001]["status"] == "not_curated"


@pytest.mark.anyio
async def test_major_data_calpoly_vs_uc(server):
    cp = payload(await server.call_tool("get_major_admit_data", {"unitid": 110422, "discipline": "Liberal"}))
    assert cp["major_affects_admission"] is True and cp["matched_college"] == "Liberal Arts"
    uc = payload(await server.call_tool("get_major_admit_data", {"unitid": 110705}))
    assert uc["major_affects_admission"] is False and uc["status"] == "not_loaded"


@pytest.fixture
def anyio_backend():
    return "asyncio"
