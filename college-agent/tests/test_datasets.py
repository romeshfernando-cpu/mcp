"""Loader behavior for partially filled source-school data."""
from college_agent.datasets import Datasets

HEADER = "campus,fall_year,high_school,city,applicants,admits,enrollees,applicant_mean_gpa,admit_mean_gpa,enrollee_mean_gpa\n"


def test_missing_counts_are_none_not_zero(data_dir):
    # GPA-only export (no count view loaded yet): counts must come back unknown.
    (data_dir / "source_school.csv").write_text(
        HEADER + "Santa Barbara,2025,Example High School,Exampleville,,,,4.10,4.30,4.25\n")
    r = Datasets().source_school(110705, "Example High School")
    assert r["status"] == "ok"
    assert r["applicants"] is None and r["admits"] is None and r["enrollees"] is None
    assert r["admit_mean_gpa"] == 4.30
