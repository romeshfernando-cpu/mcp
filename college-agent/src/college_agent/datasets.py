"""Loads the curated, sourced datasets in data/.

Rule: this layer never invents values. Missing data comes back as an explicit
status ("not_loaded", "not_curated", "insufficient_data") so Claude can say so.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("COLLEGE_AGENT_DATA", Path(__file__).resolve().parents[2] / "data"))


def _json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text())


def _csv(name: str) -> list[dict]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _int(v: str | None) -> int | None:
    n = _num(v)
    return int(n) if n is not None else None


def _num(v: str | None) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


POOL_YEARS = 3  # single-year results from one high school swing a lot; pool recent years


def _pool(rows: list[dict], years: int) -> dict | None:
    """Combine the most recent `years` fall terms that have counts.

    Admit rate = total admits / total applicants. Admit GPA is the mean of each
    year's admit GPA weighted by that year's admits, using only years that
    report both. Returns None when no year in the window has counts.
    """
    recent = sorted(rows, key=lambda r: int(r["fall_year"]), reverse=True)[:years]
    counted = [r for r in recent if _int(r["applicants"]) is not None and _int(r["admits"]) is not None]
    if not counted:
        return None
    apps = sum(_int(r["applicants"]) for r in counted)
    adms = sum(_int(r["admits"]) for r in counted)
    gpa_rows = [(r, _num(r["admit_mean_gpa"])) for r in counted if _num(r["admit_mean_gpa"]) is not None]
    gpa_w = sum(_int(r["admits"]) for r, _ in gpa_rows)
    gpa = round(sum(g * _int(r["admits"]) for r, g in gpa_rows) / gpa_w, 2) if gpa_w else None
    yrs = sorted(int(r["fall_year"]) for r in counted)
    return {
        "fall_years": yrs,
        "applicants": apps,
        "admits": adms,
        "admit_rate": round(adms / apps, 3) if apps else None,
        "admit_mean_gpa": gpa,
        "method": f"Sum of admits / sum of applicants over fall {yrs[0]}-{yrs[-1]}; "
                  "admit GPA weighted by each year's admits.",
    }


class Datasets:
    def __init__(self) -> None:
        self.schools = _json("schools.json")
        self.policies = _json("policies.json")
        self.deadlines = _json("deadlines.json")
        self.majors = _json("major_admission.json")
        self.source_rows = _csv("source_school.csv")
        self.discipline_rows = _csv("uc_discipline.csv")

    def school(self, unitid: int) -> dict:
        return self.schools.get(str(unitid), {})

    def policy(self, unitid: int) -> dict:
        system = self.school(unitid).get("system")
        return self.policies.get(system, {}) if system else {}

    def deadline(self, unitid: int) -> dict:
        key = str(unitid)
        if key in self.deadlines:
            return {"status": "verified", **self.deadlines[key]}
        if self.school(unitid).get("system") == "UC":
            return {"status": "verified", **self.deadlines["UC"]}
        return {"status": "not_curated",
                "note": "No verified deadline on file. Check the school's admissions site; do not estimate."}

    def source_school(self, unitid: int, high_school: str) -> dict:
        campus = self.school(unitid).get("uc_campus")
        if not campus:
            return {"status": "not_applicable", "note": "High-school-level data is only loaded for UC campuses."}
        if not self.source_rows:
            return {"status": "not_loaded",
                    "note": "UC admissions-by-source-school data hasn't been loaded (see data/README.md)."}
        hs = high_school.strip().lower()
        rows = [r for r in self.source_rows
                if r["campus"].strip().lower() == campus.lower() and hs in r["high_school"].strip().lower()]
        if not rows:
            return {"status": "no_match", "note": f"No rows for '{high_school}' at UC {campus}."}
        latest = max(rows, key=lambda r: int(r["fall_year"]))
        return {
            "status": "ok",
            "campus": campus,
            "fall_year": int(latest["fall_year"]),
            "high_school": latest["high_school"],
            # Blank at the source means unknown, not zero: keep it None so
            # classify_fit never treats a missing count as real evidence.
            "applicants": _int(latest["applicants"]),
            "admits": _int(latest["admits"]),
            "enrollees": _int(latest["enrollees"]),
            "admit_mean_gpa": _num(latest["admit_mean_gpa"]),
            "applicant_mean_gpa": _num(latest["applicant_mean_gpa"]),
            "pooled": _pool(rows, POOL_YEARS),
            "years_available": sorted({int(r["fall_year"]) for r in rows}),
            "gpa_basis": "UC weighted, capped 10th-11th grade GPA",
            "source_url": "https://www.universityofcalifornia.edu/about-us/information-center/admissions-source-school",
        }

    def major_data(self, unitid: int, discipline: str | None) -> dict:
        school, policy = self.school(unitid), self.policy(unitid)
        base = {"major_affects_admission": policy.get("major_affects_admission"),
                "major_note": policy.get("major_note")}
        key = school.get("major_data_key")
        if key and key in self.majors:
            m = self.majors[key]
            colleges = {
                name: {**c, "admit_rate": round(c["selected"] / c["applied"], 3)}
                for name, c in m["colleges"].items()
            }
            match = None
            if discipline:
                match = next((n for n in colleges if discipline.lower() in n.lower()), None)
            return {"status": "ok", **base, "year": m["year"], "unit": "college",
                    "colleges": colleges, "matched_college": match,
                    "gpa_scale_note": m["gpa_scale_note"], "source_url": m["source_url"]}
        campus = school.get("uc_campus")
        if campus:
            rows = [r for r in self.discipline_rows if r["campus"].strip().lower() == campus.lower()]
            if not rows:
                return {"status": "not_loaded", **base,
                        "note": "UC discipline data hasn't been loaded (see data/README.md)."}
            year = max(int(r["fall_year"]) for r in rows)
            disciplines = {
                r["discipline"]: {
                    "applicants": int(_num(r["applicants"]) or 0),
                    "admits": int(_num(r["admits"]) or 0),
                    "admit_rate": round((_num(r["admits"]) or 0) / (_num(r["applicants"]) or 1), 3),
                    "admit_gpa_25": _num(r["admit_gpa_25"]),
                    "admit_gpa_75": _num(r["admit_gpa_75"]),
                } for r in rows if int(r["fall_year"]) == year
            }
            return {"status": "ok", **base, "year": year, "unit": "broad discipline",
                    "disciplines": disciplines,
                    "caution": "UC advises using this as a general guide to selectivity, not a predictor.",
                    "source_url": "https://www.universityofcalifornia.edu/about-uc/information-center/freshman-admission-discipline"}
        return {"status": "not_curated", **base, "note": "No major-level admission data on file for this school."}
