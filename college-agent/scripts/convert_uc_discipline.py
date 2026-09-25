"""Convert UC Information Center "Freshman admission by discipline" table
exports into data/uc_discipline.csv.

The "Broad Discipline Table" crosstab has no campus or year column (they are
dashboard filters), so pass them with each file. Admit GPA range is UC's
25th-75th percentile. Blank values stay blank; nothing is estimated.

Usage:
    python scripts/convert_uc_discipline.py \
        --file "Los Angeles:2025:Broad_Discipline_Table-la.csv" \
        --file "Berkeley:2025:Broad_Discipline_Table.csv"
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from convert_uc_export import clean, read_export

OUT = Path(__file__).resolve().parents[1] / "data" / "uc_discipline.csv"
FIELDS = ["campus", "fall_year", "discipline", "applicants", "admits", "admit_gpa_25", "admit_gpa_75"]
GPA_RANGE = "Admit GPA range (25th - 75th pctl)"


def gpa_range(v: str | None) -> tuple[str, str]:
    v = (v or "").strip()
    if " - " not in v:
        return "", ""
    lo, hi = (p.strip() for p in v.split(" - ", 1))
    return lo, hi


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", action="append", required=True,
                    help='"<campus>:<fall year>:<path>", repeat per campus/year')
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    out = []
    for spec in args.file:
        campus, year, path = spec.split(":", 2)
        for r in read_export(Path(path)):
            disc = (r.get("Broad discipline") or "").strip()
            if not disc or disc.lower() in ("total", "grand total"):
                continue
            lo, hi = gpa_range(r.get(GPA_RANGE))
            out.append({"campus": campus.strip(), "fall_year": year.strip(), "discipline": disc,
                        "applicants": clean(r.get("Applicants")), "admits": clean(r.get("Admits")),
                        "admit_gpa_25": lo, "admit_gpa_75": hi})

    out.sort(key=lambda r: (r["campus"], int(r["fall_year"]), r["discipline"]))
    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"Wrote {len(out)} rows to {args.out}")


if __name__ == "__main__":
    main()
