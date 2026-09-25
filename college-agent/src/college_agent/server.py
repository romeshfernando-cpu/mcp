"""College list builder MCP server (v1).

Claude already has web search and (via connectors) Google Calendar. This server
adds only what Claude lacks: grounded admissions data, deterministic fit logic,
and verified deadlines.
"""

from __future__ import annotations

import os
from dataclasses import asdict

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import budget, fit, profiles
from .datasets import Datasets
from .scorecard import ScorecardClient

INSTRUCTIONS = """Tools for building a balanced college list for a U.S. student.
Workflow: save_student_profile -> search_colleges -> get_source_school_history /
get_major_admit_data -> classify_fit -> check_budget -> get_deadlines.
Every result carries its source and data year; cite them. When a tool reports
missing data (not_loaded, not_curated, insufficient_data), say so plainly
instead of estimating. Deadlines with early_action = null mean the school has
no early round."""

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


def build_server(scorecard: ScorecardClient | None = None,
                 datasets: Datasets | None = None) -> MCPServer:
    sc = scorecard or ScorecardClient()
    ds = datasets or Datasets()
    server = MCPServer(name="college-list-builder", instructions=INSTRUCTIONS, version="0.1.0")

    def _enrich(school: dict) -> dict:
        policy = ds.policy(school["unitid"])
        return {**school,
                "system": ds.school(school["unitid"]).get("system"),
                "test_policy": policy.get("test_policy", "unknown"),
                "major_affects_admission": policy.get("major_affects_admission")}

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, idempotent_hint=True))
    def save_student_profile(
        high_school: str,
        weighted_gpa: float | None = None,
        uc_gpa: float | None = None,
        act_composite: int | None = None,
        act_section_scores: dict[str, int] | None = None,
        act_test_date: str | None = None,
        intended_majors: list[str] | None = None,
        major_flexible: bool | None = None,
        savings: float | None = None,
        prefers_public: bool | None = None,
        home_zip: str | None = None,
        profile_id: str | None = None,
    ) -> dict:
        """Save or update the student's academic profile and return a profile_id for other tools.

        Call this first. Scores can come from the parent's message or from a
        screenshot of the student's MyACT score page (read the image, then pass
        the numbers here). uc_gpa is the UC-calculated weighted, capped
        10th-11th grade GPA; if only a weighted GPA is known, pass weighted_gpa
        and note that fit results will be less certain. Pass profile_id to
        update an existing profile.
        """
        pid = profiles.save({
            "high_school": high_school, "weighted_gpa": weighted_gpa, "uc_gpa": uc_gpa,
            "act_composite": act_composite, "act_section_scores": act_section_scores,
            "act_test_date": act_test_date, "intended_majors": intended_majors,
            "major_flexible": major_flexible, "savings": savings,
            "prefers_public": prefers_public, "home_zip": home_zip,
        }, profile_id)
        saved = profiles.get(pid)
        gaps = []
        if not saved.get("uc_gpa"):
            gaps.append("uc_gpa (ask for it, or for her 10th-11th grade A-G grades, if UCs are on the list)")
        if saved.get("savings") is None:
            gaps.append("savings or annual budget")
        return {"profile_id": pid, "profile": saved, "missing_for_best_results": gaps}

    @server.tool(annotations=READ_ONLY)
    async def search_colleges(
        state: str | None = "CA",
        ownership: str = "public",
        zip_code: str | None = None,
        distance_mi: int | None = None,
        min_admit_rate: float | None = None,
        max_admit_rate: float | None = None,
        name: str | None = None,
        limit: int = 40,
    ) -> dict:
        """Find four-year colleges from the U.S. Dept. of Education College Scorecard.

        ownership: "public", "private_nonprofit", or "any". Admit rates are
        fractions (0.3 = 30%). Returns admit rate, ACT middle 50% (act_scores_year
        says which cohort year it's from -- "latest", a fallback year, or null if
        the school has never reported), cost of attendance, average net price,
        6-year graduation rate, median earnings, plus each school's test policy
        and whether major choice affects admission (when known). Use unitid
        values with the other tools.
        """
        results = await sc.search(state=state, ownership=ownership, zip_code=zip_code,
                                  distance_mi=distance_mi, min_admit_rate=min_admit_rate,
                                  max_admit_rate=max_admit_rate, name=name, limit=limit)
        return {"count": len(results), "schools": [_enrich(s) for s in results]}

    @server.tool(annotations=READ_ONLY)
    def get_source_school_history(unitid: int, high_school: str) -> dict:
        """How applicants from the student's own high school fared at a UC campus.

        Returns applicants, admits, and mean admitted GPA for the most recent
        year from the UC Information Center. This is usually the most
        personalized signal available. Small counts are suppressed at the
        source; report 'insufficient data' rather than guessing.
        """
        return ds.source_school(unitid, high_school)

    @server.tool(annotations=READ_ONLY)
    def get_major_admit_data(unitid: int, discipline: str | None = None) -> dict:
        """Whether choice of major changes admission odds at a school, with the data.

        Check major_affects_admission first: at most UC campuses major is
        generally not a factor, while Cal Poly admits by college. Returns
        admit rates and GPA ranges by college or broad discipline.
        """
        return ds.major_data(unitid, discipline)

    @server.tool(annotations=READ_ONLY)
    async def classify_fit(profile_id: str, unitids: list[int],
                           intended_discipline: str | None = None) -> dict:
        """Label each school reach, target, or safety for this student, deterministically.

        Uses the most specific evidence available per school: her high
        school's admit rate and admitted GPA, then college/major data, then the
        overall admit rate. Ignores test scores where the school is test-blind.
        act_scores_year flags when the ACT range used isn't from the latest
        cohort (a warning is added too) -- likely because the school went
        test-optional and stopped reporting. Every label includes the evidence,
        confidence, and warnings; explain these to the parent rather than
        restating the label alone.
        """
        p = profiles.get(profile_id)
        if not p:
            return {"error": f"No profile '{profile_id}'. Call save_student_profile first."}
        gpa_verified = p.get("uc_gpa") is not None
        gpa = p.get("uc_gpa") or p.get("weighted_gpa")
        records = await sc.get_many(unitids)
        out = []
        for u in unitids:
            rec = records.get(u, {"unitid": u, "name": ds.school(u).get("name", str(u))})
            policy = ds.policy(u)
            ev = fit.SchoolEvidence(
                name=rec.get("name", str(u)),
                overall_admit_rate=rec.get("admit_rate"),
                test_policy=policy.get("test_policy", "unknown"),
                act_25=rec.get("act_25"), act_75=rec.get("act_75"),
                act_scores_year=rec.get("act_scores_year"),
            )
            src = ds.source_school(u, p["high_school"])
            if src.get("status") == "ok":
                ev.source_applicants, ev.source_admits = src["applicants"], src["admits"]
                ev.source_admit_mean_gpa = src["admit_mean_gpa"]
            major = ds.major_data(u, intended_discipline)
            if major.get("status") == "ok" and major.get("matched_college"):
                c = major["colleges"][major["matched_college"]]
                ev.major_gpa_low, ev.major_gpa_high = c["gpa_low"], c["gpa_high"]
                ev.major_admit_rate = c["admit_rate"]
                ev.gpa_scale_note = major.get("gpa_scale_note")
            result = asdict(fit.classify(ev, gpa, gpa_verified, p.get("act_composite")))
            result["unitid"] = u
            out.append(result)
        return {"student_gpa_used": gpa, "gpa_verified": gpa_verified,
                "method": "Deterministic rules; thresholds in fit.THRESHOLDS", "results": out}

    @server.tool(annotations=READ_ONLY)
    async def check_budget(unitids: list[int], profile_id: str | None = None,
                           savings: float | None = None, years: int = 4,
                           annual_increase: float = budget.DEFAULT_ANNUAL_INCREASE) -> dict:
        """Compare each school's estimated total cost over `years` against the family's savings.

        Uses full cost of attendance (in-state for publics), growing
        annual_increase per year. For private schools it also shows the average
        net price, which only applies to families receiving grant aid.
        """
        if savings is None and profile_id:
            savings = (profiles.get(profile_id) or {}).get("savings")
        if savings is None:
            return {"error": "Provide savings or a profile_id with savings saved."}
        records = await sc.get_many(unitids)
        results = []
        for u in unitids:
            r = records.get(u)
            if not r:
                results.append({"unitid": u, "status": "unknown", "note": "School not found in Scorecard."})
                continue
            results.append({"unitid": u, **budget.check(r["name"], r["ownership"], r.get("cost_of_attendance"),
                                                        r.get("avg_net_price"), savings, years, annual_increase)})
        return {"results": results, "source": "College Scorecard cost of attendance"}

    @server.tool(annotations=READ_ONLY)
    def get_deadlines(unitids: list[int]) -> dict:
        """Verified application deadlines for fall 2027 entry, with source links.

        early_action = null means the school has NO early action round; tell
        the parent that directly and offer the regular deadline instead.
        status 'not_curated' means no verified date is on file: never estimate
        one; point to the school's admissions site. Returns ISO dates suitable
        for creating calendar events.
        """
        out = []
        for u in unitids:
            d = ds.deadline(u)
            if d["status"] == "verified":
                d["early_action_available"] = d.get("early_action") is not None
            out.append({"unitid": u, "school": ds.school(u).get("name"), **d})
        return {"results": out}

    return server


def main() -> None:
    server = build_server()
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    if transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=os.environ.get("HOST", "0.0.0.0"),
                   port=int(os.environ.get("PORT", "8000")), stateless_http=True)


if __name__ == "__main__":
    main()
