# Data

Everything here is either verified from a primary source (with `source_url` and
`verified_on`) or an empty template you fill from a primary source. The server
never invents values; missing data is reported as missing.

| File | What | Status |
|---|---|---|
| `schools.json` | IPEDS unitid -> system / UC campus mapping | Verify unitids against `search_colleges` results |
| `policies.json` | Test policy and whether major affects admission, per system | Verified 2026-09-24 |
| `deadlines.json` | Fall 2027 deadlines (UC, Cal Poly SLO) | Verified 2026-09-24 |
| `major_admission.json` | Cal Poly 2025 admits by college | Verified 2026-09-24 |
| `source_school.csv` | UC applicants/admits/GPA by high school | Santa Margarita Catholic HS and Capistrano Valley HS, fall 1994-2025: counts and mean GPAs (exports 2026-09-25) |
| `uc_discipline.csv` | UC admits by broad discipline | **Empty template: fill before demo** |

## Filling `source_school.csv` (the key demo data)

1. Open https://www.universityofcalifornia.edu/about-us/information-center/admissions-source-school
2. For each UC campus you care about, search for the student's high school and
   export the table (see the page's "Data download instructions" PDF).
3. Map the export into these columns (one row per campus per year):
   `campus,fall_year,high_school,city,applicants,admits,enrollees,applicant_mean_gpa,admit_mean_gpa,enrollee_mean_gpa`
   - `campus` is the short name used in `schools.json` (e.g. `Santa Barbara`).
   - Leave a cell empty if the source suppresses it. Never fill in estimates.
4. Or let the converter do step 3 for you (it handles the UTF-16, tab-separated
   export format and joins the GPA and count views):
   `python scripts/convert_uc_export.py --gpa <gpa export> --counts <count export>` (repeat
   both flags once per school; the output is rebuilt from every file you pass)

## Filling `uc_discipline.csv`

Same process from
https://www.universityofcalifornia.edu/about-uc/information-center/freshman-admission-discipline
with columns `campus,fall_year,discipline,applicants,admits,admit_gpa_25,admit_gpa_75`.

## Adding a school's deadline

Only after reading it on the school's own site. Add an entry keyed by unitid
with `source_url` and `verified_on`. Use `null` for early_action/early_decision
only when the school confirms there is no early round.
