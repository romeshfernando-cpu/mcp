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


def test_pooled_three_years(data_dir):
    (data_dir / "source_school.csv").write_text(HEADER + "".join([
        "Santa Barbara,2022,Example High School,X,100,10,,,4.00,\n",   # outside 3-year window
        "Santa Barbara,2023,Example High School,X,100,20,,,4.10,\n",
        "Santa Barbara,2024,Example High School,X,100,40,,,4.20,\n",
        "Santa Barbara,2025,Example High School,X,100,30,,,,\n",       # GPA suppressed
    ]))
    r = Datasets().source_school(110705, "Example High School")
    assert r["fall_year"] == 2025 and r["admits"] == 30
    p = r["pooled"]
    assert p["fall_years"] == [2023, 2024, 2025]
    assert (p["applicants"], p["admits"], p["admit_rate"]) == (300, 90, 0.3)
    assert p["admit_mean_gpa"] == round((4.10 * 20 + 4.20 * 40) / 60, 2)  # 2025 has no GPA


def test_pooled_none_without_counts(data_dir):
    (data_dir / "source_school.csv").write_text(
        HEADER + "Santa Barbara,2025,Example High School,X,,,,4.10,4.30,4.25\n")
    assert Datasets().source_school(110705, "Example High School")["pooled"] is None


def test_uc_discipline_rates_and_blanks(data_dir):
    (data_dir / "uc_discipline.csv").write_text(
        "campus,fall_year,discipline,applicants,admits,admit_gpa_25,admit_gpa_75\n"
        "Santa Barbara,2025,Engineering,1000,200,4.20,4.30\n"
        "Santa Barbara,2025,Nursing,50,,,\n")
    r = Datasets().major_data(110705, "Engineering")
    assert r["status"] == "ok" and r["year"] == 2025
    assert r["disciplines"]["Engineering"]["admit_rate"] == 0.2
    nursing = r["disciplines"]["Nursing"]
    assert nursing["admits"] is None and nursing["admit_rate"] is None  # blank means unknown, not 0%
