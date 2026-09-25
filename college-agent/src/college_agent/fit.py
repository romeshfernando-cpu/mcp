"""Deterministic reach / target / safety classification.

Design choice: Claude explains the result, code computes it. Same inputs always
give the same label, and every label comes with the evidence used, so the
logic can be evaluated (see evals/) and tuned in one place.

All thresholds live in THRESHOLDS so they can be tuned against evals.
"""

from __future__ import annotations

from dataclasses import dataclass, field

THRESHOLDS = {
    "always_reach_below_rate": 0.25,  # under 25% admit rate is a reach for anyone
    "low_rate": 0.35,                 # below this, rate counts against
    "high_rate": 0.65,                # at/above this, rate counts in favor
    "gpa_margin": 0.10,               # GPA this far above/below reference moves the label
    "safety_min_rate": 0.50,          # never call a school a safety below this rate
    "min_source_applicants": 5,       # mirrors UC/SF Chronicle suppression rules
    "min_source_admits": 3,
}


@dataclass
class SchoolEvidence:
    name: str
    overall_admit_rate: float | None = None
    test_policy: str = "unknown"  # "test_blind" | "test_optional" | "test_required" | "unknown"
    act_25: float | None = None
    act_75: float | None = None
    act_scores_year: str | None = None  # "latest", a fallback year, or None; see scorecard.normalize
    # From the student's own high school (UC Information Center), if available
    source_applicants: int | None = None
    source_admits: int | None = None
    source_admit_mean_gpa: float | None = None
    # From major/college-level data (e.g. Cal Poly by college), if available
    major_gpa_low: float | None = None
    major_gpa_high: float | None = None
    major_admit_rate: float | None = None
    gpa_scale_note: str | None = None


@dataclass
class FitResult:
    school: str
    label: str  # "reach" | "target" | "safety" | "unknown"
    confidence: str  # "high" | "medium" | "low"
    admit_rate_used: float | None
    rate_source: str | None
    reference_gpa: float | None
    reference_gpa_source: str | None
    act_scores_year: str | None = None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _usable_source_data(ev: SchoolEvidence) -> bool:
    return (
        ev.source_applicants is not None
        and ev.source_admits is not None
        and ev.source_applicants >= THRESHOLDS["min_source_applicants"]
        and ev.source_admits >= THRESHOLDS["min_source_admits"]
    )


def classify(
    ev: SchoolEvidence,
    student_gpa: float | None,
    gpa_verified: bool,
    act_composite: float | None = None,
) -> FitResult:
    t = THRESHOLDS
    reasons: list[str] = []
    warnings: list[str] = []

    # 1. Pick the most specific admit rate available.
    rate, rate_source = None, None
    if _usable_source_data(ev):
        rate = ev.source_admits / ev.source_applicants
        rate_source = f"student's high school ({ev.source_admits}/{ev.source_applicants} admitted)"
    elif ev.major_admit_rate is not None:
        rate, rate_source = ev.major_admit_rate, "admit rate for the intended college/major"
    elif ev.overall_admit_rate is not None:
        rate, rate_source = ev.overall_admit_rate, "overall admit rate"
    elif ev.source_applicants is not None:
        warnings.append("High-school data exists but is too small to use (suppressed).")

    if rate is None:
        return FitResult(ev.name, "unknown", "low", None, None, None, None,
                         reasons=["No admit-rate data available."], warnings=warnings)

    # 2. Pick the most specific reference GPA available.
    ref_gpa, ref_source = None, None
    if _usable_source_data(ev) and ev.source_admit_mean_gpa is not None:
        ref_gpa, ref_source = ev.source_admit_mean_gpa, "mean GPA of admits from her high school"
    elif ev.major_gpa_low is not None and ev.major_gpa_high is not None:
        ref_gpa = round((ev.major_gpa_low + ev.major_gpa_high) / 2, 3)
        ref_source = f"midpoint of admitted GPA range {ev.major_gpa_low}-{ev.major_gpa_high}"
    if ev.gpa_scale_note:
        warnings.append(ev.gpa_scale_note)

    # 3. Score.
    score = 0.0
    if rate < t["low_rate"]:
        score -= 1
        reasons.append(f"Admit rate {rate:.0%} ({rate_source}) is selective.")
    elif rate >= t["high_rate"]:
        score += 1
        reasons.append(f"Admit rate {rate:.0%} ({rate_source}) is favorable.")
    else:
        reasons.append(f"Admit rate {rate:.0%} ({rate_source}) is moderate.")

    margin = None
    if student_gpa is not None and ref_gpa is not None:
        margin = round(student_gpa - ref_gpa, 3)
        if margin >= t["gpa_margin"]:
            score += 1
            reasons.append(f"GPA {student_gpa} is {margin:+.2f} vs reference {ref_gpa} ({ref_source}).")
        elif margin <= -t["gpa_margin"]:
            score -= 1
            reasons.append(f"GPA {student_gpa} is {margin:+.2f} vs reference {ref_gpa} ({ref_source}).")
        else:
            reasons.append(f"GPA {student_gpa} is close to reference {ref_gpa} ({ref_source}).")
    else:
        warnings.append("No comparable GPA reference; label relies on admit rate only.")

    stale_act = ev.act_scores_year not in (None, "latest")
    if ev.test_policy == "test_blind":
        reasons.append("Test scores are not considered here, so ACT was ignored.")
    elif act_composite is not None and ev.act_25 is not None and ev.act_75 is not None:
        year_note = f", {ev.act_scores_year} data" if stale_act else ""
        if act_composite >= ev.act_75:
            score += 0.5
            reasons.append(f"ACT {act_composite} is at/above the 75th percentile ({ev.act_75}{year_note}).")
        elif act_composite < ev.act_25:
            score -= 0.5
            reasons.append(f"ACT {act_composite} is below the 25th percentile ({ev.act_25}{year_note}).")
        else:
            reasons.append(f"ACT {act_composite} is within the middle 50% ({ev.act_25}-{ev.act_75}{year_note}).")
        if stale_act:
            warnings.append(
                f"ACT range is from {ev.act_scores_year}, the last year this school broadly reported "
                "scores -- it may be test-optional now, so this range may not reflect current admissions."
            )

    # 4. Label with guardrails.
    if rate < t["always_reach_below_rate"]:
        label = "reach"
        reasons.append(f"Any school under {t['always_reach_below_rate']:.0%} admit rate is a reach.")
    elif score >= 1.5 and rate >= t["safety_min_rate"]:
        label = "safety"
    elif score <= -1:
        label = "reach"
    else:
        label = "target"

    # 5. Confidence reflects how specific and verified the inputs were.
    if not gpa_verified:
        warnings.append("GPA is self-reported weighted GPA, not the UC-calculated GPA; treat as estimate.")
    if rate_source and rate_source.startswith("student's high school") and gpa_verified:
        confidence = "high"
    elif ref_gpa is not None and gpa_verified:
        confidence = "medium"
    elif ref_gpa is not None or rate_source != "overall admit rate":
        confidence = "medium" if gpa_verified else "low"
    else:
        confidence = "low"

    return FitResult(ev.name, label, confidence, round(rate, 4), rate_source,
                     ref_gpa, ref_source, act_scores_year=ev.act_scores_year,
                     reasons=reasons, warnings=warnings)
