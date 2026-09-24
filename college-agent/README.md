# College List Builder (MCP server + skill)

An agent that helps parents build a balanced college list inside Claude.
Claude already has web search and a Google Calendar connector; this server adds
only what Claude lacks:

- **Grounded data:** College Scorecard API, UC admissions-by-high-school data, Cal Poly admits by college
- **Deterministic fit logic:** reach/target/safety computed in code (`fit.py`), with evidence and confidence
- **Verified deadlines:** with source links, and explicit "no early action" where true

## Tools (v1)

| Tool | Purpose |
|---|---|
| `save_student_profile` | Store GPA, ACT (e.g. read from a MyACT screenshot), majors, budget |
| `search_colleges` | Scorecard search, enriched with test policy and major-matters flag |
| `get_source_school_history` | How applicants from her high school fared at each UC |
| `get_major_admit_data` | Whether major affects admission, with rates and GPA ranges |
| `classify_fit` | Deterministic reach/target/safety with evidence |
| `check_budget` | 4-year cost of attendance vs. savings |
| `get_deadlines` | Verified fall 2027 deadlines |

The skill in `skill/college-list-builder/` encodes the counselor workflow:
correct wrong assumptions early, one clarifying question at a time, code
classifies and Claude explains.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export SCORECARD_API_KEY=...   # free: https://api.data.gov/signup
pytest                          # 13 tests, synthetic fixtures, no network
python evals/run_fit_evals.py   # fit-logic evals
college-agent                   # serves MCP at http://localhost:8000/mcp
```

Use `MCP_TRANSPORT=stdio college-agent` to test with a local MCP client.

## Before the demo

1. Fill `data/source_school.csv` and `data/uc_discipline.csv` (see `data/README.md`).
2. Deploy somewhere with a public HTTPS URL (any Python container host works; see `Dockerfile`).
   Claude connects to remote MCP servers from Anthropic's cloud, so localhost won't work.
3. In Claude: Settings > Connectors > add custom connector with `https://<your-host>/mcp`.
4. Upload `skill/college-list-builder` as a skill (zip the folder).
5. Run the checks in `evals/agent_scenarios.md`.

## Known limits (v1)

- Profile store is a single JSON file with no auth. Profiles describe minors, so
  add auth, encryption, and a delete tool before any real use.
- Scorecard field names follow the data dictionary; if the API changes, update `scorecard.FIELDS`.
- Fit thresholds are judgment calls; tune them against `evals/fit_cases.json`.
