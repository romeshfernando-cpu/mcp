from college_agent.scorecard import normalize


def _raw(**overrides):
    base = {
        "id": 122409,
        "school.name": "San Diego State University",
        "school.city": "San Diego",
        "school.state": "CA",
        "school.ownership": 1,
        "school.school_url": "www.sdsu.edu/",
        "latest.student.size": 35377,
        "latest.admissions.admission_rate.overall": 0.3619,
        "latest.admissions.act_scores.25th_percentile.cumulative": None,
        "latest.admissions.act_scores.75th_percentile.cumulative": None,
        "latest.cost.attendance.academic_year": 30000,
        "latest.cost.avg_net_price.public": 15000,
        "latest.cost.avg_net_price.private": None,
        "latest.completion.completion_rate_4yr_150nt": 0.75,
        "latest.earnings.10_yrs_after_entry.median": 60000,
    }
    base.update(overrides)
    return base


def test_act_scores_used_directly_when_latest_has_data():
    raw = _raw(**{
        "latest.admissions.act_scores.25th_percentile.cumulative": 24,
        "latest.admissions.act_scores.75th_percentile.cumulative": 30,
    })
    out = normalize(raw)
    assert (out["act_25"], out["act_75"], out["act_scores_year"]) == (24, 30, "latest")


def test_act_scores_fall_back_to_2020_when_latest_is_null():
    raw = _raw(**{
        "2020.admissions.act_scores.25th_percentile.cumulative": 22,
        "2020.admissions.act_scores.75th_percentile.cumulative": 29,
    })
    out = normalize(raw)
    assert (out["act_25"], out["act_75"], out["act_scores_year"]) == (22, 29, "2020")


def test_act_scores_fall_back_to_2019_when_2020_is_also_null():
    raw = _raw(**{
        "2019.admissions.act_scores.25th_percentile.cumulative": 21,
        "2019.admissions.act_scores.75th_percentile.cumulative": 28,
    })
    out = normalize(raw)
    assert (out["act_25"], out["act_75"], out["act_scores_year"]) == (21, 28, "2019")


def test_act_scores_none_when_no_year_has_data():
    out = normalize(_raw())
    assert (out["act_25"], out["act_75"], out["act_scores_year"]) == (None, None, None)
