"""Test fixtures. All school numbers here are SYNTHETIC, for testing logic only."""
import json, shutil
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]

FAKE_SCHOOLS = {
    110705: {"unitid": 110705, "name": "University of California-Santa Barbara", "ownership": "public",
             "admit_rate": 0.33, "act_25": 26, "act_75": 33, "cost_of_attendance": 42000, "avg_net_price": 20000},
    110671: {"unitid": 110671, "name": "University of California-Riverside", "ownership": "public",
             "admit_rate": 0.70, "act_25": None, "act_75": None, "cost_of_attendance": 38000, "avg_net_price": 15000},
    445188: {"unitid": 445188, "name": "University of California-Merced", "ownership": "public",
             "admit_rate": 0.89, "act_25": None, "act_75": None, "cost_of_attendance": 36000, "avg_net_price": 12000},
    110422: {"unitid": 110422, "name": "California Polytechnic State University-San Luis Obispo", "ownership": "public",
             "admit_rate": 0.30, "act_25": 26, "act_75": 32, "cost_of_attendance": 40000, "avg_net_price": 25000},
    999001: {"unitid": 999001, "name": "Example Private University", "ownership": "private_nonprofit",
             "admit_rate": 0.50, "act_25": 25, "act_75": 30, "cost_of_attendance": 90000, "avg_net_price": 45000},
}


class FakeScorecard:
    async def search(self, **kw):
        own = kw.get("ownership", "any")
        return [s for s in FAKE_SCHOOLS.values() if own in ("any", s["ownership"])]

    async def get_many(self, unitids):
        return {u: FAKE_SCHOOLS[u] for u in unitids if u in FAKE_SCHOOLS}


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    shutil.copytree(ROOT / "data", d)
    shutil.copy(ROOT / "tests/fixtures/source_school.csv", d / "source_school.csv")
    # Tests use synthetic data only; start from an empty discipline file.
    shutil.copy(ROOT / "tests/fixtures/uc_discipline.csv", d / "uc_discipline.csv")
    monkeypatch.setenv("PROFILE_STORE", str(tmp_path / "profiles.json"))
    import college_agent.datasets as ds, college_agent.profiles as pr
    monkeypatch.setattr(ds, "DATA_DIR", d)
    monkeypatch.setattr(pr, "STORE", tmp_path / "profiles.json")
    return d


@pytest.fixture
def server(data_dir):
    from college_agent.server import build_server
    from college_agent.datasets import Datasets
    return build_server(scorecard=FakeScorecard(), datasets=Datasets())
