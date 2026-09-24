"""Thin client for the U.S. Department of Education College Scorecard API.

Get a free key at https://api.data.gov/signup and set SCORECARD_API_KEY.
Field names follow the Scorecard data dictionary; verify them there if the API
changes: https://collegescorecard.ed.gov/data/documentation/
"""

from __future__ import annotations

import os
from typing import Any

import httpx

BASE_URL = "https://api.data.gov/ed/collegescorecard/v1/schools"

OWNERSHIP = {"public": 1, "private_nonprofit": 2}
OWNERSHIP_NAME = {1: "public", 2: "private_nonprofit", 3: "private_for_profit"}

FIELDS = {
    "id": "unitid",
    "school.name": "name",
    "school.city": "city",
    "school.state": "state",
    "school.ownership": "ownership",
    "school.school_url": "url",
    "latest.student.size": "undergrad_size",
    "latest.admissions.admission_rate.overall": "admit_rate",
    "latest.admissions.act_scores.25th_percentile.cumulative": "act_25",
    "latest.admissions.act_scores.75th_percentile.cumulative": "act_75",
    "latest.cost.attendance.academic_year": "cost_of_attendance",
    "latest.cost.avg_net_price.public": "avg_net_price_public",
    "latest.cost.avg_net_price.private": "avg_net_price_private",
    "latest.completion.completion_rate_4yr_150nt": "grad_rate_6yr",
    "latest.earnings.10_yrs_after_entry.median": "median_earnings_10yr",
}


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    out = {short: raw.get(api) for api, short in FIELDS.items()}
    out["ownership"] = OWNERSHIP_NAME.get(out["ownership"], "unknown")
    pub, priv = out.pop("avg_net_price_public"), out.pop("avg_net_price_private")
    out["avg_net_price"] = pub if out["ownership"] == "public" else priv
    out["source"] = "U.S. Dept. of Education College Scorecard (most recent year available)"
    return out


class ScorecardClient:
    def __init__(self, api_key: str | None = None, http: httpx.AsyncClient | None = None):
        self.api_key = api_key or os.environ.get("SCORECARD_API_KEY", "")
        self.http = http or httpx.AsyncClient(timeout=20)
        self._cache: dict[int, dict] = {}

    async def _get(self, params: dict[str, Any]) -> list[dict]:
        if not self.api_key:
            raise RuntimeError("SCORECARD_API_KEY is not set (free key: https://api.data.gov/signup).")
        params = {**params, "api_key": self.api_key, "fields": ",".join(FIELDS)}
        resp = await self.http.get(BASE_URL, params=params)
        resp.raise_for_status()
        results = [normalize(r) for r in resp.json().get("results", [])]
        for r in results:
            self._cache[r["unitid"]] = r
        return results

    async def search(self, state: str | None = None, ownership: str = "any",
                     zip_code: str | None = None, distance_mi: int | None = None,
                     min_undergrads: int = 500, min_admit_rate: float | None = None,
                     max_admit_rate: float | None = None, name: str | None = None,
                     limit: int = 50) -> list[dict]:
        params: dict[str, Any] = {
            "school.degrees_awarded.predominant": 3,  # bachelor's-granting
            "school.operating": 1,
            "latest.student.size__range": f"{min_undergrads}..",
            "per_page": min(limit, 100),
            "sort": "latest.admissions.admission_rate.overall:asc",
        }
        if state:
            params["school.state"] = state
        if ownership in OWNERSHIP:
            params["school.ownership"] = OWNERSHIP[ownership]
        elif ownership == "any":
            params["school.ownership"] = "1,2"
        if zip_code and distance_mi:
            params["zip"], params["distance"] = zip_code, f"{distance_mi}mi"
        if min_admit_rate is not None or max_admit_rate is not None:
            lo = "" if min_admit_rate is None else min_admit_rate
            hi = "" if max_admit_rate is None else max_admit_rate
            params["latest.admissions.admission_rate.overall__range"] = f"{lo}..{hi}"
        if name:
            params["school.name"] = name
        return await self._get(params)

    async def get_many(self, unitids: list[int]) -> dict[int, dict]:
        missing = [u for u in unitids if u not in self._cache]
        if missing:
            await self._get({"id": ",".join(map(str, missing)), "per_page": 100})
        return {u: self._cache[u] for u in unitids if u in self._cache}
