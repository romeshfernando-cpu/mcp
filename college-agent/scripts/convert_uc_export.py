"""Convert UC Information Center "Admissions by source school" crosstab exports
into data/source_school.csv.

The UC dashboards export as UTF-16, tab-separated files (even when named .csv),
and the GPA and count views are separate downloads. This script reads either or
both, joins them on (high school, fall year, campus), and writes the columns
datasets.py expects. Values the source leaves blank stay blank; nothing is
estimated.

Usage:
    python scripts/convert_uc_export.py --gpa FR_GPA_by_Inst.csv [--counts FR_counts.csv]
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "source_school.csv"
FIELDS = ["campus", "fall_year", "high_school", "city", "applicants", "admits",
          "enrollees", "applicant_mean_gpa", "admit_mean_gpa", "enrollee_mean_gpa"]

# Export header -> our column. Several spellings accepted for the count view.
GPA_COLS = {"App GPA": "applicant_mean_gpa", "Adm GPA": "admit_mean_gpa", "Enrl GPA": "enrollee_mean_gpa"}
COUNT_COLS = {
    "applicants": ["Applicants", "App", "Apps"],
    "admits": ["Admits", "Adm", "Admit"],
    "enrollees": ["Enrollees", "Enrl", "Enrolled", "Enr"],
}


def read_export(path: Path) -> list[dict]:
    raw = path.read_bytes()
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    text = raw.decode(enc)
    delim = "\t" if "\t" in text.splitlines()[0] else ","
    return list(csv.DictReader(text.splitlines(), delimiter=delim))


def clean(v: str | None) -> str:
    # Strip whitespace and thousands separators ("1,234" -> "1234"); blank stays blank.
    return (v or "").strip().replace(",", "")


def key(r: dict) -> tuple[str, str, str]:
    return (r["School"].strip(), r["Fall term"].strip(), r["Campus"].strip())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpa", type=Path)
    ap.add_argument("--counts", type=Path)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    if not (args.gpa or args.counts):
        ap.error("pass --gpa and/or --counts")

    rows: dict[tuple, dict] = {}

    def base(r: dict) -> dict:
        k = key(r)
        if k not in rows:
            rows[k] = {f: "" for f in FIELDS} | {
                "high_school": k[0], "fall_year": k[1], "campus": k[2], "city": r.get("City", "").strip()}
        return rows[k]

    if args.gpa:
        for r in read_export(args.gpa):
            out = base(r)
            for src, dst in GPA_COLS.items():
                out[dst] = clean(r.get(src))

    if args.counts:
        data = read_export(args.counts)
        headers = data[0].keys() if data else []
        mapping = {}
        for dst, options in COUNT_COLS.items():
            match = next((h for h in headers if h.strip() in options), None)
            if not match:
                raise SystemExit(f"Counts export has no column for {dst}; headers: {list(headers)}")
            mapping[dst] = match
        for r in data:
            out = base(r)
            for dst, src in mapping.items():
                out[dst] = clean(r.get(src))

    ordered = sorted(rows.values(), key=lambda r: (r["high_school"], r["campus"], int(r["fall_year"])))
    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(ordered)
    print(f"Wrote {len(ordered)} rows to {args.out}")


if __name__ == "__main__":
    main()
