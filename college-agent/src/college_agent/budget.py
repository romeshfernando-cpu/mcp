"""Four-year cost vs. savings. Pure functions, no I/O."""

from __future__ import annotations

DEFAULT_ANNUAL_INCREASE = 0.04  # assumed yearly cost growth; overridable per call


def four_year_cost(annual_cost: float, years: int = 4,
                   annual_increase: float = DEFAULT_ANNUAL_INCREASE) -> int:
    return round(sum(annual_cost * (1 + annual_increase) ** y for y in range(years)))


def check(name: str, ownership: str, cost_of_attendance: float | None,
          avg_net_price: float | None, savings: float, years: int = 4,
          annual_increase: float = DEFAULT_ANNUAL_INCREASE) -> dict:
    if cost_of_attendance is None:
        return {"school": name, "status": "unknown",
                "note": "No cost-of-attendance data; check the school's net price calculator."}

    total = four_year_cost(cost_of_attendance, years, annual_increase)
    result = {
        "school": name,
        "annual_cost_of_attendance": round(cost_of_attendance),
        "estimated_total": total,
        "years": years,
        "assumed_annual_increase": annual_increase,
        "savings": round(savings),
        "surplus_or_shortfall": round(savings - total),
        "fits_budget": savings >= total,
        "basis": "full cost of attendance (tuition, fees, housing, food, books, other)",
    }
    if ownership == "public":
        result["note"] = "Public cost of attendance is the in-state figure."
    elif avg_net_price is not None:
        result["avg_net_price_for_aid_recipients"] = round(avg_net_price)
        result["note"] = ("Average net price applies to students who receive grant aid. "
                          "A family that doesn't qualify may pay close to full cost. "
                          "Use the school's net price calculator for a real estimate.")
    return result
