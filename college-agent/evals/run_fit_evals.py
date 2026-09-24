"""Run classify_fit evals: python evals/run_fit_evals.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from college_agent.fit import SchoolEvidence, classify  # noqa: E402

cases = json.loads((Path(__file__).parent / "fit_cases.json").read_text())["cases"]
failures = 0
for c in cases:
    r = classify(SchoolEvidence(**c["evidence"]), c["gpa"], c["gpa_verified"], c.get("act"))
    ok = r.label == c["expect"]
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {c['id']:<28} expected={c['expect']:<8} got={r.label:<8} conf={r.confidence}")
    if not ok:
        for reason in r.reasons:
            print("      -", reason)
print(f"\n{len(cases) - failures}/{len(cases)} passed")
sys.exit(1 if failures else 0)
